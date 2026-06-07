#!/usr/bin/env python3
"""Generate a seed Android planning dataset."""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from typing import Dict, List

from android_planner.data_io import split_rows, write_jsonl
from android_planner.rule_planner import RuleBasedAndroidPlanner

ANDROID_INTENTS: Dict[str, Dict[str, List[str]]] = {
    "auth": {
        "verbs": ["implement", "build", "create", "refactor", "improve"],
        "objects": [
            "login and signup flow",
            "OAuth token refresh",
            "password reset screen",
            "biometric login",
        ],
        "constraints": [
            "using Kotlin and Compose",
            "with MVVM and repository pattern",
            "with unit tests and lint checks",
            "integrated with Retrofit APIs",
        ],
    },
    "networking": {
        "verbs": ["add", "build", "design", "optimize"],
        "objects": [
            "API client layer",
            "pagination for feed API",
            "retry and timeout handling",
            "error mapping for network responses",
        ],
        "constraints": [
            "in an Android app",
            "using Retrofit and coroutines",
            "with clean architecture boundaries",
            "with offline cache fallback",
        ],
    },
    "database": {
        "verbs": ["implement", "migrate", "optimize", "stabilize"],
        "objects": [
            "Room database schema for tasks",
            "local cache invalidation strategy",
            "DAO queries for dashboard",
            "synchronization between API and Room",
        ],
        "constraints": [
            "for Android app",
            "using Kotlin data classes",
            "with instrumentation tests",
            "with repository layer updates",
        ],
    },
    "ui": {
        "verbs": ["build", "redesign", "implement", "ship"],
        "objects": [
            "Jetpack Compose profile screen",
            "navigation graph with nested routes",
            "Material 3 dashboard layout",
            "state-driven settings screen",
        ],
        "constraints": [
            "for Android 14+",
            "with Compose navigation",
            "with ViewModel state handling",
            "with UI tests for critical paths",
        ],
    },
    "quality": {
        "verbs": ["improve", "stabilize", "increase", "enforce"],
        "objects": [
            "test coverage for ViewModel layer",
            "lint and static analysis quality gate",
            "crash-free startup flow",
            "instrumentation test reliability",
        ],
        "constraints": [
            "for Android project",
            "with Gradle CI tasks",
            "with Espresso and JUnit",
            "with flaky test mitigation",
        ],
    },
}

NON_ANDROID_TEMPLATES = [
    "Create a PowerPoint deck for investor updates.",
    "Build an iOS SwiftUI shopping app checkout flow.",
    "Write a LinkedIn marketing campaign plan for SaaS launch.",
    "Improve Excel macros for monthly finance workbook.",
    "Create a Photoshop workflow for product photos.",
    "Design a WordPress blog theme for travel agency.",
    "Generate SQL queries for warehouse ETL dashboard.",
]


def build_android_prompt(rng: random.Random) -> str:
    intent = rng.choice(list(ANDROID_INTENTS.values()))
    return (
        f"{rng.choice(intent['verbs']).capitalize()} {rng.choice(intent['objects'])} "
        f"{rng.choice(intent['constraints'])}."
    )


def generate_dataset(total_android: int, total_non_android: int, seed: int) -> List[dict]:
    rng = random.Random(seed)
    planner = RuleBasedAndroidPlanner()
    rows: List[dict] = []

    for idx in range(total_android):
        prompt = build_android_prompt(rng)
        plan = planner.plan(prompt)
        rows.append(
            {
                "id": f"A-{idx:05d}",
                "prompt": prompt,
                "is_android_related": True,
                "task_plan": plan.model_dump(),
            }
        )

    for idx in range(total_non_android):
        prompt = rng.choice(NON_ANDROID_TEMPLATES)
        plan = planner.plan(prompt)
        rows.append(
            {
                "id": f"N-{idx:05d}",
                "prompt": prompt,
                "is_android_related": False,
                "task_plan": plan.model_dump(),
            }
        )
    rng.shuffle(rows)
    return rows


def write_label_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "prompt", "is_android_related"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "id": row["id"],
                    "prompt": row["prompt"],
                    "is_android_related": int(row["is_android_related"]),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate seed dataset for Android task planning.")
    parser.add_argument("--android-count", type=int, default=1200)
    parser.add_argument("--non-android-count", type=int, default=400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default="data/raw")
    args = parser.parse_args()

    rows = generate_dataset(args.android_count, args.non_android_count, args.seed)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(output_dir / "prompt_plans.jsonl", rows)
    write_label_csv(output_dir / "prompt_labels.csv", rows)

    train_rows, val_rows, test_rows = split_rows(rows, train_ratio=0.7, val_ratio=0.15, seed=args.seed)
    write_jsonl(output_dir / "train.jsonl", train_rows)
    write_jsonl(output_dir / "val.jsonl", val_rows)
    write_jsonl(output_dir / "test.jsonl", test_rows)

    print(f"Wrote {len(rows)} rows to {output_dir}")
    print(f"Train/Val/Test: {len(train_rows)}/{len(val_rows)}/{len(test_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
