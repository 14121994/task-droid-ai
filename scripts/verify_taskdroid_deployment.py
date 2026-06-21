#!/usr/bin/env python3
"""Verify the TaskDroid vLLM + API deployment chain."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_PROMPT = "Build Android login with Compose, ViewModel, Retrofit, and tests."


def _get_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _record(results: list[dict[str, Any]], name: str, passed: bool, detail: Any) -> None:
    results.append({"check": name, "passed": passed, "detail": detail})


def _check_vllm(
    results: list[dict[str, Any]],
    base_url: str,
    expected_alias: str,
    timeout: float,
    generation_timeout: float,
) -> None:
    try:
        models = _get_json(f"{base_url.rstrip('/')}/v1/models", timeout=timeout)
        model_ids = [row.get("id", "") for row in models.get("data", []) if isinstance(row, dict)]
        _record(
            results,
            "vllm_model_alias",
            expected_alias in model_ids,
            {"expected": expected_alias, "observed": model_ids},
        )
    except Exception as exc:  # noqa: BLE001
        _record(results, "vllm_model_alias", False, str(exc))
        return

    payload = {
        "model": expected_alias,
        "messages": [{"role": "user", "content": "Return JSON readiness check."}],
        "temperature": 0,
        "max_tokens": 32,
    }
    try:
        response = _post_json(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            payload,
            timeout=generation_timeout,
        )
        choices = response.get("choices", [])
        _record(
            results,
            "vllm_chat_generation",
            isinstance(choices, list) and bool(choices),
            "received chat completion choices" if choices else response,
        )
    except Exception as exc:  # noqa: BLE001
        _record(results, "vllm_chat_generation", False, str(exc))


def _check_api(
    results: list[dict[str, Any]],
    base_url: str,
    expected_alias: str,
    prompt: str,
    intelligence_level: str,
    timeout: float,
) -> None:
    try:
        health = _get_json(f"{base_url.rstrip('/')}/health", timeout=timeout)
        _record(results, "api_health_ready", health.get("ready") is True, health)
    except Exception as exc:  # noqa: BLE001
        _record(results, "api_health_ready", False, str(exc))
        return

    payload = {"prompt": prompt, "intelligence_level": intelligence_level}
    try:
        response = _post_json(f"{base_url.rstrip('/')}/plan", payload, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        _record(results, "api_plan_response", False, str(exc))
        return

    plan = response.get("plan", {})
    metadata = response.get("planner_metadata", {})
    implementation_tasks = plan.get("implementation_tasks", [])
    _record(
        results,
        "api_plan_response",
        bool(plan) and isinstance(implementation_tasks, list) and bool(implementation_tasks),
        {
            "feature_summary": plan.get("feature_summary"),
            "task_count": len(implementation_tasks) if isinstance(implementation_tasks, list) else 0,
        },
    )
    _record(
        results,
        "api_uses_vllm_without_fallback",
        response.get("backend") == "vllm"
        and response.get("requested_backend") == "vllm"
        and response.get("fallback_used") is False,
        {
            "backend": response.get("backend"),
            "requested_backend": response.get("requested_backend"),
            "fallback_used": response.get("fallback_used"),
        },
    )
    _record(
        results,
        "api_model_alias_attribution",
        metadata.get("model_alias") == expected_alias and metadata.get("served_by_fallback") is False,
        metadata,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a deployed TaskDroid planner runtime.")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("TASKDROID_API_BASE_URL", "http://127.0.0.1:8000"),
        help="TaskDroid API base URL.",
    )
    parser.add_argument(
        "--vllm-base-url",
        default=os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8001"),
        help="vLLM/OpenAI-compatible base URL.",
    )
    parser.add_argument("--expected-model-alias", default="taskdroid-android-planner-v1")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument(
        "--intelligence-level",
        choices=("low", "medium", "high", "xhigh"),
        default="high",
    )
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--vllm-timeout", type=float, default=180)
    parser.add_argument("--skip-vllm", action="store_true", help="Only check the TaskDroid API.")
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    if not args.skip_vllm:
        _check_vllm(
            results,
            base_url=args.vllm_base_url,
            expected_alias=args.expected_model_alias,
            timeout=min(args.timeout, 30),
            generation_timeout=args.vllm_timeout,
        )
    _check_api(
        results,
        base_url=args.api_base_url,
        expected_alias=args.expected_model_alias,
        prompt=args.prompt,
        intelligence_level=args.intelligence_level,
        timeout=args.timeout,
    )

    ready = all(row["passed"] for row in results)
    print(json.dumps({"ready": ready, "checks": results}, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
