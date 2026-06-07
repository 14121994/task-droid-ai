#!/usr/bin/env python3
"""Prepare SFT chat-format dataset for prompt-to-plan model fine-tuning."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from android_planner.data_io import read_jsonl, split_rows, write_jsonl

SYSTEM_PROMPT = (
    "You are an Android app planning assistant. Convert user prompts into JSON task plans with "
    "fields: is_android_related, confidence, feature_summary, files_or_modules, "
    "implementation_tasks, acceptance_checks, risks, questions_for_user."
)


def to_chat_row(row: Dict) -> Dict:
    return {
        "id": row["id"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": row["prompt"]},
            {"role": "assistant", "content": json.dumps(row["task_plan"], ensure_ascii=True)},
        ],
        "is_android_related": row["is_android_related"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build chat-style SFT dataset.")
    parser.add_argument("--input-file", type=str, default="data/raw/prompt_plans.jsonl")
    parser.add_argument("--output-dir", type=str, default="data/processed")
    parser.add_argument("--android-only", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = read_jsonl(args.input_file)
    if not rows:
        raise ValueError("No rows found. Run scripts/generate_seed_dataset.py first.")

    if args.android_only:
        rows = [r for r in rows if r["is_android_related"]]

    chat_rows: List[Dict] = [to_chat_row(r) for r in rows]
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
