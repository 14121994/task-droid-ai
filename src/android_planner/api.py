"""FastAPI application for Android prompt planning."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from .guardrails import PlanValidator, plan_with_retry
from .inference import build_backend
from .schemas import TaskPlan

IntelligenceLevel = Literal["low", "medium", "high", "xhigh"]
INTELLIGENCE_LEVELS: tuple[IntelligenceLevel, ...] = ("low", "medium", "high", "xhigh")
DEFAULT_PLANNER_NAME = "taskdroid-android-planner"
DEFAULT_PLANNER_VERSION = "1.0.0"
DEFAULT_BEHAVIOR_VERSION = "rule-intent-v25"
DEFAULT_MODEL_ALIAS = "taskdroid-android-planner-v1"


class PlanRequest(BaseModel):
    prompt: str = Field(
        min_length=3,
        max_length=4000,
        description="User request to convert into Android tasks.",
    )
    intelligence_level: IntelligenceLevel = Field(
        default="low",
        description="Planner intelligence tier to use: low, medium, high, or xhigh.",
    )

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("prompt must contain at least 3 non-whitespace characters")
        return normalized


class PlannerMetadata(BaseModel):
    planner_name: str
    planner_version: str
    behavior_version: str
    model_alias: str
    backend_kind: str
    served_by_fallback: bool


class PlanResponse(BaseModel):
    plan: TaskPlan
    intelligence_level: IntelligenceLevel
    backend: str
    requested_backend: str
    fallback_used: bool
    fallback_reason: str | None = None
    attempted_backends: list[str] = Field(default_factory=list)
    latency_ms: int
    planner_metadata: PlannerMetadata


@dataclass(frozen=True)
class BackendRoute:
    backend_name: str
    model_path: str | None
    backend: object


def create_app() -> FastAPI:
    backend_name = os.getenv("PLANNER_BACKEND", "rule")
    model_path = os.getenv("PLANNER_MODEL_PATH")
    primary_retries = _env_int("PLANNER_PRIMARY_RETRIES", default=0)
    health_generation_probe = _env_bool("PLANNER_HEALTH_GENERATION_PROBE", default=False)
    health_probe_timeout_seconds = _env_float("PLANNER_HEALTH_PROBE_TIMEOUT_SECONDS", default=3.0)

    def _env(level: IntelligenceLevel, suffix: str) -> str | None:
        return os.getenv(f"PLANNER_{level.upper()}_{suffix}")

    def _build_route(level: IntelligenceLevel) -> BackendRoute:
        level_backend_name = _env(level, "BACKEND") or backend_name
        level_model_path = _env(level, "MODEL_PATH") or model_path
        level_backend = build_backend(kind=level_backend_name, model_path=level_model_path)
        return BackendRoute(
            backend_name=level_backend_name,
            model_path=level_model_path,
            backend=level_backend,
        )

    routes = {level: _build_route(level) for level in INTELLIGENCE_LEVELS}
    validator = PlanValidator(schema_path=os.getenv("PLANNER_SCHEMA_PATH", "configs/task_plan_schema.json"))

    app = FastAPI(title="Android Task Planner API", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        readiness_cache: dict[tuple[str, str | None], dict] = {}

        def _route_readiness(level: IntelligenceLevel, route: BackendRoute) -> dict:
            key = (route.backend_name, route.model_path)
            if key in readiness_cache:
                return readiness_cache[key]
            checks = _backend_readiness(
                route.backend,
                include_generation_probe=health_generation_probe,
                timeout_seconds=health_probe_timeout_seconds,
            )
            readiness_cache[key] = checks
            return checks

        route_payloads = {}
        route_readiness = {}
        for level, route in routes.items():
            readiness = _route_readiness(level, route)
            route_readiness[level] = readiness
            route_payloads[level] = {
                "backend": route.backend_name,
                "fallback_backend": "none",
                "custom_configured": bool(
                    _env(level, "BACKEND")
                    or _env(level, "MODEL_PATH")
                ),
                "ready": readiness["ready"],
                "readiness_checks": readiness["checks"],
            }
        ready = all(checks["ready"] for checks in route_readiness.values())
        return {
            "status": "ok" if ready else "degraded",
            "ready": ready,
            "backend": backend_name,
            "fallback_backend": "none",
            "generation_probe_enabled": health_generation_probe,
            "intelligence_levels": route_payloads,
        }

    @app.post("/plan", response_model=PlanResponse)
    def plan_endpoint(request: PlanRequest) -> PlanResponse:
        started_at = time.perf_counter()
        route = routes[request.intelligence_level]
        attempted_backends = [route.backend_name]
        try:
            plan = plan_with_retry(
                lambda prompt: _plan_with_intelligence(route.backend, prompt, request.intelligence_level),
                request.prompt,
                validator,
                retries=primary_retries,
            )
            return PlanResponse(
                plan=plan,
                intelligence_level=request.intelligence_level,
                backend=route.backend_name,
                requested_backend=route.backend_name,
                fallback_used=False,
                fallback_reason=None,
                attempted_backends=attempted_backends,
                latency_ms=_elapsed_ms(started_at),
                planner_metadata=_planner_metadata(
                    level=request.intelligence_level,
                    backend_kind=route.backend_name,
                    model_path=route.model_path,
                    served_by_fallback=False,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=_status_code_for_backend_error(exc),
                detail={
                    "error": "planner_backend_error",
                    "message": str(exc),
                    "backend": route.backend_name,
                    "requested_backend": route.backend_name,
                    "fallback_used": False,
                    "fallback_backend": "none",
                    "attempted_backends": attempted_backends,
                    "latency_ms": _elapsed_ms(started_at),
                },
            ) from exc

    return app


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _plan_with_intelligence(backend: object, prompt: str, intelligence_level: IntelligenceLevel) -> TaskPlan:
    plan_fn = getattr(backend, "plan")
    if getattr(backend, "supports_intelligence_level", False):
        return plan_fn(prompt, intelligence_level=intelligence_level)
    return plan_fn(prompt)


def _planner_metadata(
    level: IntelligenceLevel,
    backend_kind: str,
    model_path: str | None,
    served_by_fallback: bool,
) -> PlannerMetadata:
    return PlannerMetadata(
        planner_name=os.getenv("PLANNER_NAME", DEFAULT_PLANNER_NAME),
        planner_version=os.getenv("PLANNER_VERSION", DEFAULT_PLANNER_VERSION),
        behavior_version=os.getenv("PLANNER_BEHAVIOR_VERSION", DEFAULT_BEHAVIOR_VERSION),
        model_alias=_model_alias(level, model_path),
        backend_kind=backend_kind,
        served_by_fallback=served_by_fallback,
    )


def _model_alias(level: IntelligenceLevel, model_path: str | None) -> str:
    level_alias = os.getenv(f"PLANNER_{level.upper()}_MODEL_ALIAS")
    if level_alias:
        return level_alias
    configured_alias = os.getenv("PLANNER_MODEL_ALIAS") or os.getenv("MODEL_ALIAS")
    if configured_alias:
        return configured_alias
    if model_path and "::" in model_path:
        return model_path.rsplit("::", maxsplit=1)[1]
    return DEFAULT_MODEL_ALIAS


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(0, parsed)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _backend_readiness(
    backend: object,
    include_generation_probe: bool,
    timeout_seconds: float,
) -> dict:
    checks = []
    model_check = getattr(backend, "check_model_available", None)
    if callable(model_check):
        checks.append(model_check(timeout_seconds=timeout_seconds))
    generation_check = getattr(backend, "check_generation_ready", None)
    if include_generation_probe and callable(generation_check):
        checks.append(generation_check(timeout_seconds=timeout_seconds))
    elif callable(generation_check):
        checks.append({"ok": None, "kind": "generation_probe", "enabled": False})

    required_checks = [check for check in checks if check.get("ok") is not None]
    return {
        "ready": all(bool(check.get("ok")) for check in required_checks),
        "checks": checks,
    }


def _status_code_for_backend_error(exc: Exception) -> int:
    message = str(exc).lower()
    if "timed out" in message:
        return 504
    if "unavailable" in message or "in-flight generation" in message:
        return 503
    if "malformed" in message or "non-json" in message:
        return 502
    return 500


app = create_app()
