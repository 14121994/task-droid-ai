#!/usr/bin/env python3
"""Validate gold review/export readiness for production training."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
    return rows


def _dupes(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row_id in ids:
        if row_id in seen:
            duplicates.add(row_id)
        seen.add(row_id)
    return sorted(duplicates)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether gold review/export is production-ready.")
    parser.add_argument("--seed-jsonl", default="data/gold/android_gold_seed_v1.jsonl")
    parser.add_argument("--review-csv", default="data/gold/android_gold_annotation_template_v1.csv")
    parser.add_argument("--approved-jsonl", default="data/gold/android_gold_v1_approved.jsonl")
    parser.add_argument("--min-approved", type=int, default=50)
    args = parser.parse_args()

    seed_rows = _read_jsonl(Path(args.seed_jsonl))
    approved_rows = _read_jsonl(Path(args.approved_jsonl))

    review_rows: list[dict] = []
    review_path = Path(args.review_csv)
    if review_path.exists():
        with review_path.open("r", encoding="utf-8", newline="") as handle:
            review_rows = list(csv.DictReader(handle))

    seed_ids = [str(row.get("id", "")) for row in seed_rows]
    review_ids = [str(row.get("id", "")) for row in review_rows]
    approved_review_ids = [
        str(row.get("id", ""))
        for row in review_rows
        if str(row.get("approved", "")).strip().lower() == "yes"
    ]
    approved_export_ids = [str(row.get("id", "")) for row in approved_rows]

    seed_set = set(seed_ids)
    review_set = set(review_ids)
    approved_review_set = set(approved_review_ids)
    approved_export_set = set(approved_export_ids)

    errors: list[str] = []
    warnings: list[str] = []

    if not seed_rows:
        errors.append(f"Seed dataset is empty or missing: {args.seed_jsonl}")
    if not review_rows:
        errors.append(f"Review CSV is empty or missing: {args.review_csv}")
    if _dupes(seed_ids):
        errors.append("Duplicate ids detected in seed JSONL.")
    if _dupes(review_ids):
        errors.append("Duplicate ids detected in review CSV.")
    if _dupes(approved_export_ids):
        errors.append("Duplicate ids detected in approved export JSONL.")

    unknown_review_ids = sorted(review_set - seed_set)
    if unknown_review_ids:
        errors.append(f"Review CSV contains ids not present in seed set ({len(unknown_review_ids)}).")

    missing_review_ids = sorted(seed_set - review_set)
    if missing_review_ids:
        errors.append(f"Review CSV is missing seed ids ({len(missing_review_ids)}).")

    unknown_approved_ids = sorted(approved_export_set - seed_set)
    if unknown_approved_ids:
        errors.append(f"Approved JSONL contains ids not present in seed set ({len(unknown_approved_ids)}).")

    if approved_review_set != approved_export_set:
        warnings.append(
            "Approved rows in review CSV and approved export JSONL do not match. "
            "Run scripts/build_gold_approved_dataset.py after review updates."
        )

    if len(approved_review_set) < args.min_approved:
        errors.append(
            f"Approved rows in review CSV ({len(approved_review_set)}) is below minimum required ({args.min_approved})."
        )
    if len(approved_export_set) < args.min_approved:
        errors.append(
            "Approved rows in export JSONL "
            f"({len(approved_export_set)}) is below minimum required "
            f"({args.min_approved})."
        )

    summary = {
        "seed_count": len(seed_rows),
        "review_count": len(review_rows),
        "approved_marked_count": len(approved_review_set),
        "approved_exported_count": len(approved_export_set),
        "min_approved_required": args.min_approved,
        "warnings": warnings,
        "errors": errors,
        "ready": not errors,
    }
    print(json.dumps(summary, indent=2))

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
