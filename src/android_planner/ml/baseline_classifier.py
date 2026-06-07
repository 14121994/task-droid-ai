"""Classical ML baseline for Android prompt relevance detection."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


class SklearnAndroidClassifier:
    """TF-IDF + logistic regression baseline."""

    def __init__(self) -> None:
        self.pipeline = Pipeline(
            steps=[
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=20000)),
                ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
            ]
        )

    def fit(self, prompts: Iterable[str], labels: Iterable[int]) -> "SklearnAndroidClassifier":
        self.pipeline.fit(list(prompts), list(labels))
        return self

    def predict(self, prompts: Iterable[str]) -> np.ndarray:
        return self.pipeline.predict(list(prompts))

    def predict_proba(self, prompts: Iterable[str]) -> np.ndarray:
        return self.pipeline.predict_proba(list(prompts))

    def save(self, path: str | Path) -> None:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("wb") as handle:
            pickle.dump(self.pipeline, handle)

    @classmethod
    def load(cls, path: str | Path) -> "SklearnAndroidClassifier":
        file_path = Path(path)
        with file_path.open("rb") as handle:
            pipeline = pickle.load(handle)
        obj = cls()
        obj.pipeline = pipeline
        return obj
