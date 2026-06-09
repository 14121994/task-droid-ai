"""vLLM OpenAI-compatible backend for structured planner inference."""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from typing import Dict

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
                content = body["choices"][0]["message"]["content"]
                return TaskPlan.model_validate(self._extract_json_object(content))
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
            except (KeyError, ValueError, json.JSONDecodeError) as exc:
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
            return TaskPlan.model_validate(self._extract_json_object(completion_text))
        except urllib.error.HTTPError as exc:
            error_text = self._read_http_error(exc)
            raise VLLMBackendError(
                f"vLLM completion request failed with HTTP {exc.code}: {error_text[:300]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise VLLMBackendError(f"vLLM endpoint is unavailable: {exc.reason}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise VLLMBackendError(f"vLLM request timed out after {self.request_timeout_seconds:g}s.") from exc
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
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
