#!/usr/bin/env python3
"""Build approved gold dataset from reviewer decisions."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from android_planner.data_io import read_jsonl, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="Export approved gold examples to JSONL.")
    parser.add_argument(
        "--seed-jsonl",
        type=str,
        default="data/gold/android_gold_seed_v1.jsonl",
    )
    parser.add_argument(
        "--review-csv",
        type=str,
        default="data/gold/android_gold_annotation_template_v1.csv",
    )
    parser.add_argument(
        "--output-jsonl",
        type=str,
        default="data/gold/android_gold_v1_approved.jsonl",
    )
    args = parser.parse_args()

    rows = read_jsonl(args.seed_jsonl)
    by_id = {row["id"]: row for row in rows}
    approved = []

    with Path(args.review_csv).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for review in reader:
            if review.get("approved", "").strip().lower() != "yes":
                continue
            row_id = review["id"]
            if row_id not in by_id:
                continue
            row = dict(by_id[row_id])
            row["review_status"] = "approved"
            row["review_notes"] = review.get("review_notes", "")
            approved.append(row)

    write_jsonl(args.output_jsonl, approved)
    print(f"Exported {len(approved)} approved rows to {args.output_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
