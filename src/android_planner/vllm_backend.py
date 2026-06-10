"""vLLM OpenAI-compatible backend for structured planner inference."""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from typing import Any, Dict

from pydantic import ValidationError

from .prompting import build_completion_prompt, build_planner_messages
from .schemas import TaskPlan


class VLLMBackendError(RuntimeError):
    """Raised when the configured vLLM endpoint cannot serve the request."""


class VLLMPlannerBackend:
    supports_intelligence_level = True

    def __init__(
        self,
        base_url: str,
        model_name: str,
        request_timeout_seconds: float = 300.0,
        completion_max_tokens: int = 256,
        api_mode: str = "chat",
        use_response_format: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.request_timeout_seconds = request_timeout_seconds
        self.completion_max_tokens = max(1, completion_max_tokens)
        self.api_mode = self._normalize_api_mode(api_mode)
        self.use_response_format = use_response_format
        self._request_lock = threading.Lock()
        self._unhealthy_error: str | None = None

    def plan(self, prompt: str, intelligence_level: str = "medium") -> TaskPlan:
        if self._unhealthy_error:
            raise VLLMBackendError(self._unhealthy_error)
        if not self._request_lock.acquire(blocking=False):
            raise VLLMBackendError(
                "vLLM backend already has an in-flight generation; refusing to queue another request."
            )
        try:
            return self._plan_unlocked(prompt, intelligence_level=intelligence_level)
        except VLLMBackendError as exc:
            if "timed out" in str(exc).lower():
                self._unhealthy_error = (
                    f"{exc} vLLM may still be processing the abandoned request; restart the vLLM service "
                    "before serving more planner traffic."
                )
            raise
        finally:
            self._request_lock.release()

    def check_model_available(self, timeout_seconds: float | None = None) -> dict:
        timeout = self._normalized_timeout(timeout_seconds)
        try:
            body = self._get_json("/v1/models", timeout_seconds=timeout)
        except VLLMBackendError as exc:
            return {"ok": False, "kind": "model_listing", "error": str(exc)}
        model_ids = [row.get("id", "") for row in body.get("data", []) if isinstance(row, dict)]
        return {
            "ok": self.model_name in model_ids,
            "kind": "model_listing",
            "model_alias": self.model_name,
            "observed_models": model_ids,
            "error": None if self.model_name in model_ids else f"model alias {self.model_name!r} not listed",
        }

    def check_generation_ready(self, timeout_seconds: float | None = None) -> dict:
        if self._unhealthy_error:
            return {"ok": False, "kind": "generation_probe", "error": self._unhealthy_error}
        timeout = self._normalized_timeout(timeout_seconds)
        payload = {
            "model": self.model_name,
            "temperature": 0,
            "prompt": "{}",
            "max_tokens": 1,
        }
        try:
            body = self._post_json("/v1/completions", payload, timeout_seconds=timeout)
        except VLLMBackendError as exc:
            return {"ok": False, "kind": "generation_probe", "error": str(exc)}
        choices = body.get("choices")
        ok = isinstance(choices, list) and bool(choices)
        return {
            "ok": ok,
            "kind": "generation_probe",
            "model_alias": self.model_name,
            "error": None if ok else "vLLM generation probe returned no choices",
        }

    def _plan_unlocked(self, prompt: str, intelligence_level: str = "medium") -> TaskPlan:
        if self.api_mode == "chat":
            payload: Dict = {
                "model": self.model_name,
                "temperature": 0,
                "messages": build_planner_messages(prompt, intelligence_level),
                "max_tokens": self.completion_max_tokens,
            }
            if self.use_response_format:
                payload["response_format"] = {"type": "json_object"}
            try:
                body = self._post_json("/v1/chat/completions", payload)
                content = body["choices"][0]["message"].get("content") or ""
                return self._validate_task_plan(self._extract_json_object(content))
            except urllib.error.HTTPError as exc:
                error_text = self._read_http_error(exc)
                if not self._should_fallback_to_completions(exc.code, error_text):
                    raise VLLMBackendError(
                        f"vLLM chat request failed with HTTP {exc.code}: {error_text[:300]}"
                    ) from exc
            except urllib.error.URLError as exc:
                raise VLLMBackendError(f"vLLM endpoint is unavailable: {exc.reason}") from exc
            except (TimeoutError, socket.timeout) as exc:
                raise VLLMBackendError(
                    f"vLLM request timed out after {self.request_timeout_seconds:g}s."
                ) from exc
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
                raise VLLMBackendError("vLLM returned malformed or non-JSON planner output.") from exc

        completion_payload: Dict = {
            "model": self.model_name,
            "temperature": 0,
            "prompt": build_completion_prompt(prompt, intelligence_level),
            "max_tokens": self.completion_max_tokens,
        }
        try:
            completion_body = self._post_json("/v1/completions", completion_payload)
            completion_text = completion_body["choices"][0]["text"]
            return self._validate_task_plan(self._extract_json_object(completion_text))
        except urllib.error.HTTPError as exc:
            error_text = self._read_http_error(exc)
            raise VLLMBackendError(
                f"vLLM completion request failed with HTTP {exc.code}: {error_text[:300]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise VLLMBackendError(f"vLLM endpoint is unavailable: {exc.reason}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise VLLMBackendError(f"vLLM request timed out after {self.request_timeout_seconds:g}s.") from exc
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            raise VLLMBackendError("vLLM returned malformed or non-JSON planner output.") from exc

    def _post_json(self, path: str, payload: Dict, timeout_seconds: float | None = None) -> Dict:
        request = urllib.request.Request(
            url=f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._urlopen_json(request, timeout_seconds)

    def _get_json(self, path: str, timeout_seconds: float | None = None) -> Dict:
        request = urllib.request.Request(url=f"{self.base_url}{path}", method="GET")
        return self._urlopen_json(request, timeout_seconds)

    def _urlopen_json(self, request: urllib.request.Request, timeout_seconds: float | None) -> Dict:
        timeout = self._normalized_timeout(timeout_seconds)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(reason).lower():
                raise VLLMBackendError(f"vLLM request timed out after {timeout:g}s.") from exc
            raise
        except (TimeoutError, socket.timeout) as exc:
            raise VLLMBackendError(f"vLLM request timed out after {timeout:g}s.") from exc

    @staticmethod
    def _extract_json_object(text: str) -> Dict:
        decoder = json.JSONDecoder()
        for index, character in enumerate(text):
            if character != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        raise ValueError("Model output did not include a JSON object.")

    @classmethod
    def _validate_task_plan(cls, raw_plan: Dict) -> TaskPlan:
        return TaskPlan.model_validate(cls._normalize_plan_object(raw_plan))

    @classmethod
    def _normalize_plan_object(cls, raw_plan: Dict) -> Dict:
        plan = cls._unwrap_plan_object(raw_plan)
        normalized = dict(plan)

        if "feature_summary" not in normalized:
            normalized["feature_summary"] = (
                normalized.get("summary")
                or normalized.get("title")
                or normalized.get("description")
                or "Android implementation plan"
            )
        normalized["is_android_related"] = cls._coerce_bool(normalized.get("is_android_related"), default=True)
        normalized["confidence"] = cls._coerce_score(normalized.get("confidence"), default=0.75)
        normalized["plan_quality_score"] = cls._coerce_score(
            normalized.get("plan_quality_score", normalized.get("quality_score")),
            default=min(float(normalized["confidence"]), 0.8),
        )
        normalized["confidence_reasons"] = cls._coerce_string_list(
            normalized.get("confidence_reasons", normalized.get("confidence_reason")),
            default=["Model output normalized to planner schema"],
        )
        normalized["plan_category"] = cls._normalize_plan_category(normalized.get("plan_category"))
        normalized["refusal_category"] = cls._normalize_refusal_category(normalized.get("refusal_category"))
        normalized["detected_intents"] = cls._normalize_intents(normalized.get("detected_intents"))
        normalized["requires_user_clarification"] = cls._coerce_bool(
            normalized.get("requires_user_clarification"),
            default=False,
        )
        normalized["files_or_modules"] = cls._coerce_string_list(
            normalized.get("files_or_modules", normalized.get("files", normalized.get("modules"))),
        )
        normalized["implementation_tasks"] = cls._normalize_tasks(
            normalized.get("implementation_tasks", normalized.get("tasks")),
            fallback_summary=str(normalized["feature_summary"]),
        )
        normalized["acceptance_checks"] = cls._coerce_string_list(
            normalized.get("acceptance_checks", normalized.get("acceptance_criteria", normalized.get("tests"))),
        )
        normalized["risks"] = cls._coerce_string_list(normalized.get("risks"))
        normalized["questions_for_user"] = cls._coerce_string_list(
            normalized.get("questions_for_user", normalized.get("questions")),
        )
        return normalized

    @classmethod
    def _unwrap_plan_object(cls, value: Dict) -> Dict:
        for key in ("plan", "task_plan", "android_plan", "planner_output", "result", "response"):
            nested = value.get(key)
            if isinstance(nested, dict) and cls._looks_like_plan(nested):
                return nested
        return value

    @staticmethod
    def _looks_like_plan(value: Dict) -> bool:
        plan_keys = {
            "is_android_related",
            "feature_summary",
            "summary",
            "implementation_tasks",
            "tasks",
            "acceptance_checks",
            "risks",
        }
        return any(key in value for key in plan_keys)

    @classmethod
    def _normalize_tasks(cls, value: Any, fallback_summary: str) -> list[dict[str, Any]]:
        rows = value if isinstance(value, list) else cls._coerce_string_list(value)
        tasks: list[dict[str, Any]] = []
        for index, item in enumerate(rows, start=1):
            task_id = f"T{index}"
            if isinstance(item, dict):
                task = dict(item)
                title = cls._first_string(
                    task.get("title"),
                    task.get("name"),
                    task.get("task"),
                    task.get("summary"),
                    default=f"Task {index}",
                )
                description = cls._first_string(
                    task.get("description"),
                    task.get("details"),
                    task.get("implementation"),
                    task.get("summary"),
                    default=title,
                )
                layer_hint = cls._first_string(
                    task.get("layer"),
                    task.get("area"),
                    task.get("component"),
                    task.get("owner"),
                    task.get("module"),
                    default=f"{title} {description}",
                )
                task_id = cls._first_string(task.get("id"), task.get("task_id"), default=task_id)
                tasks.append(
                    {
                        "id": task_id,
                        "title": title,
                        "description": description,
                        "layer": cls._normalize_layer(layer_hint),
                        "estimated_effort": cls._normalize_effort(
                            task.get("estimated_effort", task.get("effort", task.get("size")))
                        ),
                        "dependencies": cls._coerce_string_list(
                            task.get("dependencies", task.get("depends_on", task.get("dependsOn")))
                        ),
                    }
                )
            else:
                title = str(item).strip() or f"Task {index}"
                tasks.append(
                    {
                        "id": task_id,
                        "title": title[:80],
                        "description": title,
                        "layer": cls._normalize_layer(title),
                        "estimated_effort": "M",
                        "dependencies": [],
                    }
                )

        if tasks:
            return tasks
        return [
            {
                "id": "T1",
                "title": fallback_summary[:80],
                "description": fallback_summary,
                "layer": "cross-cutting",
                "estimated_effort": "M",
                "dependencies": [],
            }
        ]

    @staticmethod
    def _normalize_layer(value: Any) -> str:
        text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
        if any(token in text for token in ("viewmodel", "view model", "compose", "screen", "ui", "presentation")):
            return "ui"
        if any(
            token in text
            for token in ("repository", "repo", "data", "api", "network", "database", "storage", "credential")
        ):
            return "data"
        if any(token in text for token in ("domain", "use case", "usecase", "state model")):
            return "domain"
        if any(token in text for token in ("test", "unit", "instrumentation", "espresso", "robolectric")):
            return "testing"
        if any(token in text for token in ("gradle", "build", "ci", "release")):
            return "build"
        if any(token in text for token in ("security", "analytics", "navigation", "architecture", "module", "di")):
            return "cross-cutting"
        return "cross-cutting"

    @staticmethod
    def _normalize_effort(value: Any) -> str:
        text = str(value or "").strip().lower()
        if text in {"s", "small"} or text.startswith(("low", "short", "simple")):
            return "S"
        if text in {"l", "large"} or text.startswith(("high", "long", "complex")):
            return "L"
        return "M"

    @staticmethod
    def _normalize_plan_category(value: Any) -> str:
        text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if text in {"discovery", "unsafe_refusal", "non_android_refusal"}:
            return text
        return "implementation"

    @staticmethod
    def _normalize_refusal_category(value: Any) -> str:
        text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if text in {"unsafe_android_request", "non_android_request"}:
            return text
        return "none"

    @classmethod
    def _normalize_intents(cls, value: Any) -> list[str]:
        known = {
            "crash_triage",
            "gradle_build",
            "security_privacy",
            "permissions_privacy",
            "performance",
            "accessibility",
            "database",
            "dependency_injection",
            "modularization",
            "release_deployment",
            "background_work",
            "notifications",
            "location_maps",
            "media_camera",
            "billing_payments",
            "analytics",
            "localization",
            "deep_links",
            "authentication",
            "networking",
            "ui_compose",
            "testing_quality",
        }
        mapped: list[str] = []
        for raw in cls._coerce_string_list(value):
            text = raw.strip().lower().replace("-", "_").replace(" ", "_")
            if text in known:
                intent = text
            elif any(token in text for token in ("auth", "login", "signin", "sign_in", "passkey", "credential")):
                intent = "authentication"
            elif any(token in text for token in ("test", "unit", "quality", "regression")):
                intent = "testing_quality"
            elif any(token in text for token in ("compose", "ui", "screen")):
                intent = "ui_compose"
            elif any(token in text for token in ("network", "api", "retrofit")):
                intent = "networking"
            else:
                continue
            if intent not in mapped:
                mapped.append(intent)
        return mapped

    @staticmethod
    def _coerce_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "y"}:
            return True
        if text in {"0", "false", "no", "n"}:
            return False
        return default

    @staticmethod
    def _coerce_score(value: Any, default: float) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return default
        if score > 1.0:
            score /= 100.0
        return min(1.0, max(0.0, score))

    @staticmethod
    def _coerce_string_list(value: Any, default: list[str] | None = None) -> list[str]:
        if value is None:
            return list(default or [])
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        if not text or text.lower() in {"none", "n/a", "no", "no questions"}:
            return list(default or [])
        return [text]

    @staticmethod
    def _first_string(*values: Any, default: str) -> str:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return default

    @staticmethod
    def _read_http_error(exc: urllib.error.HTTPError) -> str:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        return body or str(exc)

    @staticmethod
    def _should_fallback_to_completions(status_code: int, error_text: str) -> bool:
        lowered = error_text.lower()
        return (
            "chat template" in lowered
            or "chattemplateresolutionerror" in lowered
            or status_code in {404, 405}
        )

    @staticmethod
    def _normalize_api_mode(api_mode: str) -> str:
        normalized = api_mode.strip().lower()
        if normalized == "completions":
            normalized = "completion"
        return normalized if normalized in {"chat", "completion"} else "chat"

    def _normalized_timeout(self, timeout_seconds: float | None) -> float:
        if timeout_seconds is None:
            return self.request_timeout_seconds
        return timeout_seconds if timeout_seconds > 0 else self.request_timeout_seconds
