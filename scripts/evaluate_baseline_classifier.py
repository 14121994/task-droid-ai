#!/usr/bin/env python3
"""Evaluate trained baseline classifier on held-out test split."""

from __future__ import annotations

import argparse
import json

from sklearn.metrics import classification_report, confusion_matrix

from android_planner.data_io import read_jsonl
from android_planner.ml import SklearnAndroidClassifier


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate baseline Android relevance classifier.")
    parser.add_argument("--model-path", type=str, default="data/models/sklearn_android_classifier.pkl")
    parser.add_argument("--test-file", type=str, default="data/raw/test.jsonl")
    parser.add_argument("--report-path", type=str, default="data/reports/sklearn_test_report.json")
    args = parser.parse_args()

    rows = read_jsonl(args.test_file)
    if not rows:
        raise ValueError("No test rows found. Run scripts/generate_seed_dataset.py first.")

    prompts = [row["prompt"] for row in rows]
    labels = [int(row["is_android_related"]) for row in rows]

    model = SklearnAndroidClassifier.load(args.model_path)
    preds = model.predict(prompts).tolist()

    report = classification_report(labels, preds, output_dict=True, zero_division=0)
    cm = confusion_matrix(labels, preds).tolist()

    payload = {"classification_report": report, "confusion_matrix": cm}
    with open(args.report_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2) + "\n")

    print(json.dumps(payload, indent=2))
    print(f"Saved report to {args.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
