#!/usr/bin/env python3
"""Production release gates for Android planner model."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _http_get_json(url: str, timeout: int = 10) -> dict[str, Any]:
    request = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict[str, Any], timeout: int = 300) -> dict[str, Any]:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _record(results: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    results.append({"check": name, "passed": passed, "detail": detail})


def _run_pytest() -> tuple[bool, str]:
    command = [sys.executable, "-m", "pytest", "-q"]
    process = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    combined = (process.stdout + "\n" + process.stderr).strip()
    return process.returncode == 0, combined


def main() -> int:
    parser = argparse.ArgumentParser(description="Run production release gates.")
    parser.add_argument("--planner-report", default="data/reports/planner_quality_report.json")
    parser.add_argument("--approved-jsonl", default="data/gold/android_gold_v1_approved.jsonl")
    parser.add_argument("--min-schema-validity", type=float, default=0.98)
    parser.add_argument("--min-domain-accuracy", type=float, default=0.90)
    parser.add_argument("--min-eval-examples", type=int, default=200)
    parser.add_argument("--min-approved", type=int, default=50)
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--check-runtime", action="store_true")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--vllm-base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--expected-model-alias", default="taskdroid-android-planner-v1")
    args = parser.parse_args()

    checks: list[dict[str, Any]] = []

    try:
        report = _read_json(Path(args.planner_report))
    except Exception as exc:  # noqa: BLE001
        _record(checks, "planner_report_present", False, str(exc))
        print(json.dumps({"ready": False, "checks": checks}, indent=2))
        return 1

    total_examples = int(report.get("total_examples", 0))
    schema_validity = float(report.get("schema_validity_rate", 0.0))
    domain_accuracy = float(report.get("android_relevance_accuracy", 0.0))

    _record(
        checks,
        "min_eval_examples",
        total_examples >= args.min_eval_examples,
        f"observed={total_examples}, required>={args.min_eval_examples}",
    )
    _record(
        checks,
        "schema_validity_rate",
        schema_validity >= args.min_schema_validity,
        f"observed={schema_validity:.4f}, required>={args.min_schema_validity:.4f}",
    )
    _record(
        checks,
        "android_relevance_accuracy",
        domain_accuracy >= args.min_domain_accuracy,
        f"observed={domain_accuracy:.4f}, required>={args.min_domain_accuracy:.4f}",
    )

    approved_rows = _read_jsonl(Path(args.approved_jsonl))
    _record(
        checks,
        "min_approved_gold_rows",
        len(approved_rows) >= args.min_approved,
        f"observed={len(approved_rows)}, required>={args.min_approved}",
    )

    if args.run_tests:
        passed, output = _run_pytest()
        _record(checks, "pytest", passed, output.splitlines()[-1] if output else "no output")

    if args.check_runtime:
        try:
            health = _http_get_json(f"{args.api_base_url.rstrip('/')}/health")
            health_ok = health.get("status") == "ok"
            _record(checks, "runtime_api_health", health_ok, json.dumps(health))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            _record(checks, "runtime_api_health", False, str(exc))

        try:
            models = _http_get_json(f"{args.vllm_base_url.rstrip('/')}/v1/models")
            model_ids = [row.get("id", "") for row in models.get("data", [])]
            alias_ok = args.expected_model_alias in model_ids
            _record(
                checks,
                "runtime_model_alias",
                alias_ok,
                f"expected={args.expected_model_alias}, observed={model_ids}",
            )
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            _record(checks, "runtime_model_alias", False, str(exc))

        try:
            plan_payload = {
                "prompt": "Create Android Jetpack Compose settings screen with ViewModel and tests."
            }
            plan_response = _http_post_json(f"{args.api_base_url.rstrip('/')}/plan", plan_payload)
            plan = plan_response.get("plan", {})
            plan_ok = bool(plan) and isinstance(plan.get("implementation_tasks", []), list)
            _record(checks, "runtime_plan_endpoint", plan_ok, "received plan response")
            primary_ok = (
                plan_response.get("fallback_used") is False
                and plan_response.get("backend") == plan_response.get("requested_backend")
            )
            _record(
                checks,
                "runtime_plan_uses_primary_backend",
                primary_ok,
                (
                    f"backend={plan_response.get('backend')}, "
                    f"requested_backend={plan_response.get('requested_backend')}, "
                    f"fallback_used={plan_response.get('fallback_used')}"
                ),
            )
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            _record(checks, "runtime_plan_endpoint", False, str(exc))
            _record(checks, "runtime_plan_uses_primary_backend", False, str(exc))

    ready = all(check["passed"] for check in checks)
    print(json.dumps({"ready": ready, "checks": checks}, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
