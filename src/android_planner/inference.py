"""Inference backends for Android planning."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Optional

from .rule_planner import RuleBasedAndroidPlanner
from .schemas import TaskPlan

SYSTEM_PROMPT = (
    "You are an Android app planning assistant. Return only JSON with fields: "
    "is_android_related, confidence, plan_quality_score, confidence_reasons, plan_category, refusal_category, "
    "detected_intents, requires_user_clarification, feature_summary, files_or_modules, implementation_tasks, "
    "acceptance_checks, risks, questions_for_user."
)


class PlannerBackend(ABC):
    @abstractmethod
    def plan(self, prompt: str) -> TaskPlan:
        raise NotImplementedError


class RulePlannerBackend(PlannerBackend):
    supports_intelligence_level = True

    def __init__(self) -> None:
        self._planner = RuleBasedAndroidPlanner()

    def plan(self, prompt: str, intelligence_level: str = "medium") -> TaskPlan:
        return self._planner.plan(prompt, intelligence_level=intelligence_level)  # type: ignore[arg-type]


class HuggingFacePlannerBackend(PlannerBackend):
    """Optional backend for local fine-tuned models."""

    def __init__(self, model_path: str, max_new_tokens: int = 1024):
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("transformers is required for HF backend") from exc

        self._tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True)
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        self._model = AutoModelForCausalLM.from_pretrained(model_path, device_map="auto")
        self._max_new_tokens = max_new_tokens

    def plan(self, prompt: str) -> TaskPlan:
        prompt_text = self._build_prompt(prompt)
        inputs = self._tokenizer(prompt_text, return_tensors="pt").to(self._model.device)
        output = self._model.generate(
            **inputs,
            max_new_tokens=self._max_new_tokens,
            do_sample=False,
            temperature=0.0,
        )
        text = self._tokenizer.decode(output[0], skip_special_tokens=True)
        parsed = self._parse_json(text)
        return TaskPlan.model_validate(parsed)

    def _build_prompt(self, prompt: str) -> str:
        if hasattr(self._tokenizer, "apply_chat_template"):
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            return self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        return f"{SYSTEM_PROMPT}\nUser: {prompt}\nAssistant:"

    @staticmethod
    def _parse_json(text: str) -> dict:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model output did not include JSON object.")
        json_text = text[start : end + 1]
        return json.loads(json_text)


def build_backend(kind: str, model_path: Optional[str] = None) -> PlannerBackend:
    if kind == "rule":
        return RulePlannerBackend()
    if kind == "hf":
        if not model_path:
            raise ValueError("model_path is required for hf backend.")
        return HuggingFacePlannerBackend(model_path=model_path)
    if kind == "vllm":
        if not model_path:
            raise ValueError("For vllm backend, model_path must be 'base_url::model_name'.")
        from .vllm_backend import VLLMPlannerBackend

        if "::" not in model_path:
            raise ValueError("Invalid vllm config; expected 'base_url::model_name'.")
        base_url, model_name = model_path.split("::", 1)
        timeout_seconds = _env_float("PLANNER_VLLM_TIMEOUT_SECONDS", default=25.0)
        completion_max_tokens = _env_int("PLANNER_VLLM_COMPLETION_MAX_TOKENS", default=160)
        api_mode = os.getenv("PLANNER_VLLM_API_MODE", "chat")
        use_response_format = _env_bool("PLANNER_VLLM_RESPONSE_FORMAT_JSON", default=False)
        return VLLMPlannerBackend(
            base_url=base_url,
            model_name=model_name,
            request_timeout_seconds=timeout_seconds,
            completion_max_tokens=completion_max_tokens,
            api_mode=api_mode,
            use_response_format=use_response_format,
        )  # type: ignore[return-value]
    raise ValueError(f"Unsupported backend: {kind}")


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
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
