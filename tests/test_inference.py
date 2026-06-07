import sys
from types import SimpleNamespace

import pytest

from android_planner.inference import HuggingFacePlannerBackend, build_backend
from android_planner.vllm_backend import VLLMPlannerBackend


def _task_plan_json() -> str:
    return """
    {
      "is_android_related": true,
      "confidence": 0.9,
      "feature_summary": "Build Android login",
      "files_or_modules": ["app/src/main/java/LoginScreen.kt"],
      "implementation_tasks": [
        {
          "id": "T1",
          "title": "Build UI",
          "description": "Create Compose UI",
          "layer": "ui",
          "estimated_effort": "M",
          "dependencies": []
        }
      ],
      "acceptance_checks": ["./gradlew testDebugUnitTest"],
      "risks": ["API mismatch"],
      "questions_for_user": ["Which auth provider?"]
    }
    """


class _FakeInputs(dict):
    def to(self, device):
        self["device"] = device
        return self


class _FakeModel:
    device = "cpu"

    def __init__(self):
        self.generate_kwargs = None

    def generate(self, **kwargs):
        self.generate_kwargs = kwargs
        return [[101]]


class _TemplateTokenizer:
    pad_token = None
    eos_token = "<eos>"

    def __init__(self):
        self.prompt_text = None
        self.messages = None

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):  # noqa: ANN001
        self.messages = messages
        assert tokenize is False
        assert add_generation_prompt is True
        return "CHAT_PROMPT"

    def __call__(self, prompt_text, return_tensors):  # noqa: ANN001
        self.prompt_text = prompt_text
        assert return_tensors == "pt"
        return _FakeInputs({"input_ids": [1]})

    def decode(self, output, skip_special_tokens):  # noqa: ANN001
        assert output == [101]
        assert skip_special_tokens is True
        return f"prefix {_task_plan_json()} suffix"


class _PlainTokenizer:
    pad_token = "<pad>"
    eos_token = "<eos>"

    def __call__(self, prompt_text, return_tensors):  # noqa: ANN001
        return _FakeInputs({"input_ids": [1]})

    def decode(self, output, skip_special_tokens):  # noqa: ANN001
        return _task_plan_json()


def _install_fake_transformers(monkeypatch, tokenizer):
    model = _FakeModel()

    class FakeAutoTokenizer:
        @staticmethod
        def from_pretrained(model_path, use_fast):  # noqa: ANN001
            assert model_path == "fake-model"
            assert use_fast is True
            return tokenizer

    class FakeAutoModelForCausalLM:
        @staticmethod
        def from_pretrained(model_path, device_map):  # noqa: ANN001
            assert model_path == "fake-model"
            assert device_map == "auto"
            return model

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(AutoModelForCausalLM=FakeAutoModelForCausalLM, AutoTokenizer=FakeAutoTokenizer),
    )
    return model


def test_vllm_backend_uses_safe_env_defaults_for_invalid_numbers(monkeypatch):
    monkeypatch.setenv("PLANNER_VLLM_TIMEOUT_SECONDS", "not-a-number")
    monkeypatch.setenv("PLANNER_VLLM_COMPLETION_MAX_TOKENS", "-5")
    monkeypatch.setenv("PLANNER_VLLM_API_MODE", "invalid")
    monkeypatch.setenv("PLANNER_VLLM_RESPONSE_FORMAT_JSON", "invalid")

    backend = build_backend("vllm", "http://127.0.0.1:8001::taskdroid-test")

    assert isinstance(backend, VLLMPlannerBackend)
    assert backend.request_timeout_seconds == 25.0
    assert backend.completion_max_tokens == 160
    assert backend.api_mode == "chat"
    assert backend.use_response_format is False


def test_vllm_backend_uses_valid_env_numbers(monkeypatch):
    monkeypatch.setenv("PLANNER_VLLM_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("PLANNER_VLLM_COMPLETION_MAX_TOKENS", "2048")
    monkeypatch.setenv("PLANNER_VLLM_API_MODE", "completion")
    monkeypatch.setenv("PLANNER_VLLM_RESPONSE_FORMAT_JSON", "true")

    backend = build_backend("vllm", "http://127.0.0.1:8001::taskdroid-test")

    assert isinstance(backend, VLLMPlannerBackend)
    assert backend.request_timeout_seconds == 2.5
    assert backend.completion_max_tokens == 2048
    assert backend.api_mode == "completion"
    assert backend.use_response_format is True


def test_build_backend_rejects_missing_or_invalid_model_paths(monkeypatch):
    monkeypatch.delenv("PLANNER_VLLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("PLANNER_VLLM_COMPLETION_MAX_TOKENS", raising=False)
    monkeypatch.delenv("PLANNER_VLLM_API_MODE", raising=False)
    monkeypatch.delenv("PLANNER_VLLM_RESPONSE_FORMAT_JSON", raising=False)

    rule_backend = build_backend("rule")
    assert rule_backend.plan("Build Android Compose login.").is_android_related is True

    with pytest.raises(ValueError, match="model_path is required"):
        build_backend("hf")
    with pytest.raises(ValueError, match="must be 'base_url::model_name'"):
        build_backend("vllm")
    with pytest.raises(ValueError, match="Invalid vllm config"):
        build_backend("vllm", "http://127.0.0.1:8001")
    with pytest.raises(ValueError, match="Unsupported backend"):
        build_backend("unknown")

    backend = build_backend("vllm", "http://127.0.0.1:8001::taskdroid-test")
    assert backend.request_timeout_seconds == 25.0
    assert backend.completion_max_tokens == 160
    assert backend.use_response_format is False


def test_vllm_backend_uses_false_env_bool(monkeypatch):
    monkeypatch.setenv("PLANNER_VLLM_RESPONSE_FORMAT_JSON", "off")

    backend = build_backend("vllm", "http://127.0.0.1:8001::taskdroid-test")

    assert backend.use_response_format is False


def test_huggingface_backend_generates_plan_with_chat_template(monkeypatch):
    tokenizer = _TemplateTokenizer()
    model = _install_fake_transformers(monkeypatch, tokenizer)

    backend = HuggingFacePlannerBackend("fake-model", max_new_tokens=77)
    plan = backend.plan("Build Android login screen")

    assert tokenizer.pad_token == "<eos>"
    assert tokenizer.prompt_text == "CHAT_PROMPT"
    assert tokenizer.messages[0]["role"] == "system"
    assert model.generate_kwargs["max_new_tokens"] == 77
    assert model.generate_kwargs["do_sample"] is False
    assert plan.feature_summary == "Build Android login"


def test_huggingface_backend_builds_plain_prompt_without_chat_template(monkeypatch):
    tokenizer = _PlainTokenizer()
    _install_fake_transformers(monkeypatch, tokenizer)

    backend = HuggingFacePlannerBackend("fake-model")
    prompt = backend._build_prompt("Build Android login screen")

    assert "User: Build Android login screen" in prompt
    assert prompt.endswith("Assistant:")


def test_huggingface_backend_reports_missing_transformers(monkeypatch):
    monkeypatch.setitem(sys.modules, "transformers", None)

    with pytest.raises(RuntimeError, match="transformers is required"):
        HuggingFacePlannerBackend("fake-model")


def test_huggingface_backend_rejects_output_without_json():
    with pytest.raises(ValueError, match="did not include JSON"):
        HuggingFacePlannerBackend._parse_json("no json here")
