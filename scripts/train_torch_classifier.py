#!/usr/bin/env python3
"""Train a small PyTorch classifier for Android relevance."""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import List, Tuple

import numpy as np
import torch
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from android_planner.data_io import read_jsonl


class RelevanceNet(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def _extract(rows: List[dict]) -> Tuple[List[str], np.ndarray]:
    prompts = [row["prompt"] for row in rows]
    labels = np.array([int(row["is_android_related"]) for row in rows], dtype=np.float32)
    return prompts, labels


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train PyTorch Android relevance model.")
    parser.add_argument("--train-file", type=str, default="data/raw/train.jsonl")
    parser.add_argument("--val-file", type=str, default="data/raw/val.jsonl")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--max-features", type=int, default=5000)
    parser.add_argument("--model-path", type=str, default="data/models/torch_android_classifier.pt")
    parser.add_argument("--vectorizer-path", type=str, default="data/models/torch_vectorizer.pkl")
    parser.add_argument("--metrics-path", type=str, default="data/reports/torch_classifier_metrics.json")
    args = parser.parse_args()

    train_rows = read_jsonl(args.train_file)
    val_rows = read_jsonl(args.val_file)
    if not train_rows or not val_rows:
        raise ValueError("Dataset split files not found. Run scripts/generate_seed_dataset.py first.")

    x_train_text, y_train = _extract(train_rows)
    x_val_text, y_val = _extract(val_rows)

    vectorizer = CountVectorizer(max_features=args.max_features, ngram_range=(1, 2))
    x_train = vectorizer.fit_transform(x_train_text).toarray().astype(np.float32)
    x_val = vectorizer.transform(x_val_text).toarray().astype(np.float32)

    train_ds = TensorDataset(
        torch.from_numpy(x_train),
        torch.from_numpy(y_train.reshape(-1, 1)),
    )
    val_x = torch.from_numpy(x_val)
    loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)

    model = RelevanceNet(input_dim=x_train.shape[1])
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    model.train()
    for _ in range(args.epochs):
        for features, labels in loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(features)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()

    model.eval()
    with torch.no_grad():
        val_logits = model(val_x).squeeze(1).numpy()
    preds = (val_logits >= 0.0).astype(int)
    metrics = _metrics(y_val.astype(int), preds)

    model_path = Path(args.model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "input_dim": x_train.shape[1]}, model_path)

    vectorizer_path = Path(args.vectorizer_path)
    vectorizer_path.parent.mkdir(parents=True, exist_ok=True)
    with vectorizer_path.open("wb") as handle:
        pickle.dump(vectorizer, handle)

    metrics_path = Path(args.metrics_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    print(f"Saved torch model to {model_path}")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
