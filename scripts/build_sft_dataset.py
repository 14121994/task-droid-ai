#!/usr/bin/env python3
"""Prepare SFT chat-format dataset for prompt-to-plan model fine-tuning."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from android_planner.data_io import read_jsonl, split_rows, write_jsonl
from android_planner.prompting import INTELLIGENCE_LEVELS, IntelligenceLevel, build_planner_messages
from android_planner.rule_planner import RuleBasedAndroidPlanner
from android_planner.schemas import TaskPlan


def _validated_plan_payload(payload: Dict) -> Dict:
    return TaskPlan.model_validate(payload).model_dump(mode="json")


def to_chat_row(row: Dict, intelligence_level: str = "medium", task_plan: Dict | None = None) -> Dict:
    level = intelligence_level if intelligence_level in INTELLIGENCE_LEVELS else "medium"
    plan_payload = _validated_plan_payload(task_plan or row["task_plan"])
    return {
        "id": row["id"] if intelligence_level == "medium" and task_plan is None else f"{row['id']}-{level}",
        "messages": [
            *build_planner_messages(row["prompt"], level),
            {"role": "assistant", "content": json.dumps(plan_payload, ensure_ascii=True)},
        ],
        "is_android_related": plan_payload["is_android_related"],
        "intelligence_level": level,
        "source_id": row["id"],
    }


def build_chat_rows(
    rows: List[Dict],
    expand_intelligence_levels: bool = False,
    intelligence_levels: list[IntelligenceLevel] | None = None,
) -> List[Dict]:
    if not expand_intelligence_levels:
        return [to_chat_row(row) for row in rows]

    planner = RuleBasedAndroidPlanner()
    levels = intelligence_levels or list(INTELLIGENCE_LEVELS)
    chat_rows: List[Dict] = []
    for row in rows:
        for level in levels:
            plan = planner.plan(row["prompt"], intelligence_level=level)
            chat_rows.append(to_chat_row(row, intelligence_level=level, task_plan=plan.model_dump(mode="json")))
    return chat_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build chat-style SFT dataset.")
    parser.add_argument("--input-file", type=str, default="data/raw/prompt_plans.jsonl")
    parser.add_argument("--output-dir", type=str, default="data/processed")
    parser.add_argument("--android-only", action="store_true")
    parser.add_argument(
        "--expand-intelligence-levels",
        action="store_true",
        help="Generate one SFT target per selected intelligence level using the current rule planner.",
    )
    parser.add_argument(
        "--intelligence-levels",
        nargs="+",
        choices=INTELLIGENCE_LEVELS,
        default=list(INTELLIGENCE_LEVELS),
        help="Levels to generate when --expand-intelligence-levels is set.",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    rows = read_jsonl(args.input_file)
    if not rows:
        raise ValueError("No rows found. Run scripts/generate_seed_dataset.py first.")

    if args.android_only:
        rows = [r for r in rows if r["is_android_related"]]

    chat_rows = build_chat_rows(
        rows,
        expand_intelligence_levels=args.expand_intelligence_levels,
        intelligence_levels=args.intelligence_levels,
    )
    train_rows, val_rows, test_rows = split_rows(chat_rows, train_ratio=0.7, val_ratio=0.15, seed=args.seed)

    out_dir = Path(args.output_dir)
    write_jsonl(out_dir / "sft_all.jsonl", chat_rows)
    write_jsonl(out_dir / "sft_train.jsonl", train_rows)
    write_jsonl(out_dir / "sft_val.jsonl", val_rows)
    write_jsonl(out_dir / "sft_test.jsonl", test_rows)

    print(f"Prepared {len(chat_rows)} SFT examples in {out_dir}")
    print(f"SFT splits train/val/test: {len(train_rows)}/{len(val_rows)}/{len(test_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
