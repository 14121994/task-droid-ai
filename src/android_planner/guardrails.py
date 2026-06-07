"""Validation and retry guardrails for planner output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from jsonschema import validate

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
    for _ in range(retries + 1):
        try:
            plan = plan_fn(prompt)
            validator.validate_plan(plan)
            return plan
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    if retries == 0 and last_error is not None:
        raise last_error
    raise RuntimeError(f"Planner failed validation after retries: {last_error}") from last_error
