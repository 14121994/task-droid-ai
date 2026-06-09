"""Validation and retry guardrails for planner output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from jsonschema import ValidationError, validate

from .schemas import TaskPlan


class PlanValidator:
    def __init__(self, schema_path: str = "configs/task_plan_schema.json") -> None:
        self._schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))

    def validate_plan(self, plan: TaskPlan) -> None:
        validate(instance=plan.model_dump(), schema=self._schema)


def plan_with_retry(
    plan_fn: Callable[[str], TaskPlan],
    prompt: str,
    validator: PlanValidator,
    retries: int = 1,
) -> TaskPlan:
    last_error: Exception | None = None
    current_prompt = prompt
    for attempt in range(retries + 1):
        try:
            plan = plan_fn(current_prompt)
            validator.validate_plan(plan)
            return plan
        except ValidationError as exc:
            last_error = exc
            if attempt >= retries:
                break
            current_prompt = _build_validation_retry_prompt(prompt, exc)
    if last_error is not None:
        if retries == 0:
            raise last_error
        raise RuntimeError(f"Planner failed validation after retries: {last_error}") from last_error
    raise RuntimeError(f"Planner failed validation after retries: {last_error}") from last_error


def _build_validation_retry_prompt(prompt: str, error: ValidationError) -> str:
    return (
        f"{prompt}\n\n"
        "The previous planner JSON failed schema validation. Regenerate the plan from scratch. "
        "Return exactly one JSON object and no markdown or prose. Preserve the user's Android request, "
        "but fix every schema issue below.\n"
        f"Validation error: {error.message}\n"
        "For detected_intents, use only these enum ids: crash_triage, gradle_build, security_privacy, "
        "permissions_privacy, performance, accessibility, database, dependency_injection, modularization, "
        "release_deployment, background_work, notifications, location_maps, media_camera, billing_payments, "
        "analytics, localization, deep_links, authentication, networking, ui_compose, testing_quality. "
        "Map passkeys, sign-in, login, account recovery, OAuth, biometrics, credentials, sessions, and tokens "
        "to authentication. Map unit tests, instrumentation tests, QA, validation, and regression coverage "
        "to testing_quality."
    )
