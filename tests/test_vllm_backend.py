import io
import json
from urllib.error import HTTPError, URLError

import pytest

from android_planner.vllm_backend import VLLMBackendError, VLLMPlannerBackend


def _sample_plan_dict() -> dict:
    return {
        "is_android_related": True,
        "confidence": 0.88,
        "feature_summary": "Build Android login feature",
        "files_or_modules": ["app/src/main/java/com/example/auth/LoginScreen.kt"],
        "implementation_tasks": [
            {
                "id": "T1",
                "title": "Create login UI",
                "description": "Build a Compose login screen with validation.",
                "layer": "ui",
                "estimated_effort": "M",
                "dependencies": [],
            }
        ],
        "acceptance_checks": ["./gradlew testDebugUnitTest --no-daemon"],
        "risks": ["API contract mismatch"],
        "questions_for_user": ["Should login support SSO?"],
    }


def test_vllm_backend_uses_chat_completions(monkeypatch):
    plan_dict = _sample_plan_dict()
    calls = []
    payloads = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def read(self) -> bytes:
            payload = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(plan_dict),
                        }
                    }
                ]
            }
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        calls.append(request.full_url)
        payloads.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(base_url="http://127.0.0.1:8001", model_name="chat-model")
    plan = backend.plan("Build Android login flow")

    assert plan.feature_summary == plan_dict["feature_summary"]
    assert calls == ["http://127.0.0.1:8001/v1/chat/completions"]
    assert payloads[0]["max_tokens"] == 256
    assert "response_format" not in payloads[0]


def test_vllm_backend_can_opt_into_chat_response_format(monkeypatch):
    plan_dict = _sample_plan_dict()
    payloads = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def read(self) -> bytes:
            payload = {"choices": [{"message": {"content": json.dumps(plan_dict)}}]}
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        payloads.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(
        base_url="http://127.0.0.1:8001",
        model_name="chat-model",
        use_response_format=True,
    )
    backend.plan("Build Android login flow")

    assert payloads[0]["response_format"] == {"type": "json_object"}


def test_vllm_backend_completion_mode_skips_chat_completions(monkeypatch):
    plan_dict = _sample_plan_dict()
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def read(self) -> bytes:
            payload = {"choices": [{"text": json.dumps(plan_dict)}]}
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        calls.append(request.full_url)
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(
        base_url="http://127.0.0.1:8001",
        model_name="base-model",
        api_mode="completion",
    )
    plan = backend.plan("Build Android login flow")

    assert plan.feature_summary == plan_dict["feature_summary"]
    assert calls == ["http://127.0.0.1:8001/v1/completions"]


def test_vllm_backend_extracts_noisy_chat_json_with_braces_in_strings(monkeypatch):
    plan_dict = _sample_plan_dict()
    plan_dict["questions_for_user"] = ["Should the UI show literal braces like {retry}?"]

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def read(self) -> bytes:
            content = f"Here is the JSON:\n{json.dumps(plan_dict)}\nDone."
            payload = {"choices": [{"message": {"content": content}}]}
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(base_url="http://127.0.0.1:8001", model_name="chat-model")
    plan = backend.plan("Build Android login flow")

    assert plan.questions_for_user == ["Should the UI show literal braces like {retry}?"]


def test_vllm_backend_uses_configured_timeout(monkeypatch):
    plan_dict = _sample_plan_dict()
    observed_timeouts = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def read(self) -> bytes:
            payload = {"choices": [{"message": {"content": json.dumps(plan_dict)}}]}
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        observed_timeouts.append(timeout)
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(
        base_url="http://127.0.0.1:8001",
        model_name="chat-model",
        request_timeout_seconds=2.5,
    )
    backend.plan("Build Android login flow")

    assert observed_timeouts == [2.5]


def test_vllm_backend_uses_configured_completion_max_tokens(monkeypatch):
    plan_dict = _sample_plan_dict()
    observed_payloads = []

    class FakeResponse:
        def __init__(self, payload: dict):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        payload = json.loads(request.data.decode("utf-8"))
        observed_payloads.append(payload)
        if request.full_url.endswith("/v1/chat/completions"):
            body = b'{"error":{"message":"ChatTemplateResolutionError: no chat template"}}'
            raise HTTPError(
                request.full_url,
                500,
                "Internal Server Error",
                hdrs=None,
                fp=io.BytesIO(body),
            )
        return FakeResponse({"choices": [{"text": json.dumps(plan_dict)}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(
        base_url="http://127.0.0.1:8001",
        model_name="base-model",
        completion_max_tokens=1536,
    )
    backend.plan("Build Android login flow")

    assert observed_payloads[-1]["max_tokens"] == 1536


def test_vllm_backend_checks_model_availability(monkeypatch):
    observed = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def read(self) -> bytes:
            payload = {"data": [{"id": "taskdroid-android-planner-v1"}]}
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(request, timeout=60):  # noqa: ANN001
        observed.append((request.full_url, timeout))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(
        base_url="http://127.0.0.1:8001",
        model_name="taskdroid-android-planner-v1",
    )
    result = backend.check_model_available(timeout_seconds=1.5)

    assert result["ok"] is True
    assert observed == [("http://127.0.0.1:8001/v1/models", 1.5)]


def test_vllm_backend_checks_generation_readiness(monkeypatch):
    observed_payloads = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def read(self) -> bytes:
            return json.dumps({"choices": [{"text": "{"}]}).encode("utf-8")

    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        observed_payloads.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(
        base_url="http://127.0.0.1:8001",
        model_name="taskdroid-android-planner-v1",
    )
    result = backend.check_generation_ready(timeout_seconds=2.0)

    assert result["ok"] is True
    assert observed_payloads == [
        {
            "model": "taskdroid-android-planner-v1",
            "temperature": 0,
            "prompt": "{}",
            "max_tokens": 1,
        }
    ]


def test_vllm_backend_generation_readiness_reports_timeout(monkeypatch):
    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(base_url="http://127.0.0.1:8001", model_name="base-model")
    result = backend.check_generation_ready(timeout_seconds=0.5)

    assert result["ok"] is False
    assert result["kind"] == "generation_probe"
    assert "timed out" in result["error"]


def test_vllm_backend_falls_back_to_completions_on_chat_template_error(monkeypatch):
    plan_dict = _sample_plan_dict()
    calls = []

    class FakeResponse:
        def __init__(self, payload: dict):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        calls.append(request.full_url)
        if request.full_url.endswith("/v1/chat/completions"):
            body = b'{"error":{"message":"ChatTemplateResolutionError: no chat template"}}'
            raise HTTPError(
                request.full_url,
                500,
                "Internal Server Error",
                hdrs=None,
                fp=io.BytesIO(body),
            )
        if request.full_url.endswith("/v1/completions"):
            payload = {"choices": [{"text": f"noise {json.dumps(plan_dict)} trailing"}]}
            return FakeResponse(payload)
        raise AssertionError(f"Unexpected URL: {request.full_url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(base_url="http://127.0.0.1:8001", model_name="base-model")
    plan = backend.plan("Build Android login flow")

    assert plan.is_android_related is True
    assert calls == [
        "http://127.0.0.1:8001/v1/chat/completions",
        "http://127.0.0.1:8001/v1/completions",
    ]


def test_vllm_backend_raises_when_model_output_is_unusable(monkeypatch):
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def read(self) -> bytes:
            return json.dumps({"choices": [{"text": "not json"}]}).encode("utf-8")

    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        calls.append(request.full_url)
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(base_url="http://127.0.0.1:8001", model_name="base-model")

    with pytest.raises(VLLMBackendError, match="malformed or non-JSON"):
        backend.plan(
            "Plan Android work for CameraX profile photo upload with permission flow and tests.",
            intelligence_level="xhigh",
        )

    assert calls == [
        "http://127.0.0.1:8001/v1/chat/completions",
    ]


def test_vllm_backend_raises_when_endpoint_is_unavailable(monkeypatch):
    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        raise URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(base_url="http://127.0.0.1:8001", model_name="base-model")

    with pytest.raises(VLLMBackendError, match="unavailable"):
        backend.plan("Build Android login flow")


def test_vllm_backend_raises_when_request_times_out(monkeypatch):
    calls = 0

    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        nonlocal calls
        calls += 1
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(
        base_url="http://127.0.0.1:8001",
        model_name="base-model",
        request_timeout_seconds=3,
    )

    with pytest.raises(VLLMBackendError, match="timed out after 3s"):
        backend.plan("Build Android login flow")

    with pytest.raises(VLLMBackendError, match="restart the vLLM service"):
        backend.plan("Build Android settings flow")
    assert calls == 1

    readiness = backend.check_generation_ready(timeout_seconds=1)
    assert readiness["ok"] is False
    assert "restart the vLLM service" in readiness["error"]


def test_vllm_backend_refuses_to_queue_while_generation_is_in_flight():
    backend = VLLMPlannerBackend(base_url="http://127.0.0.1:8001", model_name="base-model")
    backend._request_lock.acquire()  # noqa: SLF001
    try:
        with pytest.raises(VLLMBackendError, match="in-flight generation"):
            backend.plan("Build Android login flow")
    finally:
        backend._request_lock.release()  # noqa: SLF001


def test_vllm_backend_raises_on_non_retriable_chat_http_error(monkeypatch):
    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        body = b'{"error":{"message":"context length exceeded"}}'
        raise HTTPError(request.full_url, 400, "Bad Request", hdrs=None, fp=io.BytesIO(body))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(base_url="http://127.0.0.1:8001", model_name="base-model")

    with pytest.raises(VLLMBackendError, match="chat request failed with HTTP 400"):
        backend.plan("Build Android login flow")


def test_vllm_backend_raises_on_completion_http_error(monkeypatch):
    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        body = b'{"error":{"message":"completion failed"}}'
        raise HTTPError(request.full_url, 500, "Internal Server Error", hdrs=None, fp=io.BytesIO(body))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(
        base_url="http://127.0.0.1:8001",
        model_name="base-model",
        api_mode="completion",
    )

    with pytest.raises(VLLMBackendError, match="completion request failed with HTTP 500"):
        backend.plan("Build Android login flow")


def test_vllm_backend_raises_on_completion_url_error(monkeypatch):
    def fake_urlopen(request, timeout=60):  # noqa: ANN001, ARG001
        raise URLError("connection reset")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    backend = VLLMPlannerBackend(
        base_url="http://127.0.0.1:8001",
        model_name="base-model",
        api_mode="completion",
    )

    with pytest.raises(VLLMBackendError, match="unavailable"):
        backend.plan("Build Android login flow")


def test_vllm_backend_handles_unreadable_http_error_body():
    class UnreadableError(HTTPError):
        def read(self):  # noqa: D102
            raise OSError("cannot read")

    error = UnreadableError("http://127.0.0.1:8001", 500, "Broken", hdrs=None, fp=None)

    assert "Broken" in VLLMPlannerBackend._read_http_error(error)
    assert VLLMPlannerBackend._normalize_api_mode("completions") == "completion"
