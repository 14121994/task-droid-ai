#!/usr/bin/env python3
"""Train TF-IDF + logistic regression Android relevance baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Tuple

import mlflow
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from android_planner.data_io import read_jsonl
from android_planner.ml import SklearnAndroidClassifier


def _extract(rows: List[dict]) -> Tuple[List[str], List[int]]:
    prompts = [row["prompt"] for row in rows]
    labels = [int(row["is_android_related"]) for row in rows]
    return prompts, labels


def _metrics(y_true: List[int], y_pred: List[int]) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train baseline Android relevance classifier.")
    parser.add_argument("--train-file", type=str, default="data/raw/train.jsonl")
    parser.add_argument("--val-file", type=str, default="data/raw/val.jsonl")
    parser.add_argument("--model-path", type=str, default="data/models/sklearn_android_classifier.pkl")
    parser.add_argument("--metrics-path", type=str, default="data/reports/sklearn_baseline_metrics.json")
    parser.add_argument("--use-mlflow", action="store_true")
    args = parser.parse_args()

    train_rows = read_jsonl(args.train_file)
    val_rows = read_jsonl(args.val_file)
    if not train_rows or not val_rows:
        raise ValueError("Dataset split files not found. Run scripts/generate_seed_dataset.py first.")

    x_train, y_train = _extract(train_rows)
    x_val, y_val = _extract(val_rows)

    model = SklearnAndroidClassifier().fit(x_train, y_train)
    preds = model.predict(x_val).tolist()
    metrics = _metrics(y_val, preds)

    model.save(args.model_path)
    metrics_path = Path(args.metrics_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    if args.use_mlflow:
        mlflow.set_experiment("android_planner_baselines")
        with mlflow.start_run(run_name="tfidf_logreg"):
            mlflow.log_params({"model": "tfidf+logreg", "train_rows": len(train_rows)})
            mlflow.log_metrics(metrics)
            mlflow.log_artifact(args.model_path)
            mlflow.log_artifact(args.metrics_path)

    print(f"Saved model to {args.model_path}")
    print(f"Validation metrics: {json.dumps(metrics, indent=2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
