#!/usr/bin/env python3
"""Evaluate planner output quality on held-out prompts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from jsonschema import ValidationError, validate

from android_planner.data_io import read_jsonl
from android_planner.rule_planner import RuleBasedAndroidPlanner


def _load_schema(path: str) -> Dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate planner output quality.")
    parser.add_argument("--test-file", type=str, default="data/raw/test.jsonl")
    parser.add_argument("--schema-file", type=str, default="configs/task_plan_schema.json")
    parser.add_argument("--report-path", type=str, default="data/reports/planner_quality_report.json")
    args = parser.parse_args()

    rows = read_jsonl(args.test_file)
    if not rows:
        raise ValueError("Test dataset missing. Run scripts/generate_seed_dataset.py first.")

    schema = _load_schema(args.schema_file)
    planner = RuleBasedAndroidPlanner()

    total = len(rows)
    valid_json = 0
    correct_domain = 0
    avg_tasks = 0.0
    failures: List[Dict] = []

    for row in rows:
        generated = planner.plan(row["prompt"]).model_dump()
        try:
            validate(instance=generated, schema=schema)
            valid_json += 1
        except ValidationError as exc:
            failures.append({"id": row["id"], "kind": "schema", "error": str(exc)})

        expected = bool(row["is_android_related"])
        predicted = bool(generated["is_android_related"])
        if expected == predicted:
            correct_domain += 1
        else:
            failures.append({"id": row["id"], "kind": "domain", "error": f"expected={expected} got={predicted}"})

        avg_tasks += len(generated["implementation_tasks"])

    report = {
        "total_examples": total,
        "schema_validity_rate": valid_json / total if total else 0.0,
        "android_relevance_accuracy": correct_domain / total if total else 0.0,
        "avg_task_count": avg_tasks / total if total else 0.0,
        "sample_failures": failures[:20],
    }

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"Saved report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
