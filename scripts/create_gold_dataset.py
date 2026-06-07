#!/usr/bin/env python3
"""Create a curated Android gold dataset and annotation template."""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from typing import Dict, List

from android_planner.data_io import write_jsonl
from android_planner.rule_planner import RuleBasedAndroidPlanner

CATEGORIES: Dict[str, Dict[str, List[str]]] = {
    "authentication": {
        "verbs": ["Implement", "Refactor", "Harden", "Stabilize", "Ship"],
        "objects": [
            "login and signup flow",
            "biometric authentication flow",
            "session refresh and logout flow",
            "password reset and OTP verification journey",
            "multi-step onboarding with account creation",
        ],
        "context": [
            "in a Kotlin Android app using MVVM and Compose",
            "using Retrofit and token-based auth",
            "with clean architecture boundaries",
            "with offline-aware state handling",
            "targeting Android 12+ and Material 3",
        ],
        "constraints": [
            "include edge-case handling for expired tokens",
            "include test coverage for ViewModel and repository",
            "include explicit error messaging strategy",
            "include analytics events for success and failure states",
            "include accessibility requirements for forms",
        ],
    },
    "networking": {
        "verbs": ["Build", "Design", "Improve", "Migrate", "Optimize"],
        "objects": [
            "network layer for feed pagination",
            "resilient API client with retry policy",
            "repository sync flow for remote-first data",
            "error mapping strategy for API failures",
            "background refresh flow with WorkManager",
        ],
        "context": [
            "for an Android app using Retrofit and coroutines",
            "in a modularized Android project",
            "using Kotlin serialization",
            "with Hilt dependency injection",
            "for a Jetpack Compose app",
        ],
        "constraints": [
            "handle HTTP timeout and 429 backoff scenarios",
            "include optimistic UI updates",
            "include loading, empty, and failure UI states",
            "ensure logs are safe and redact sensitive fields",
            "include unit and integration testing strategy",
        ],
    },
    "database": {
        "verbs": ["Create", "Refine", "Migrate", "Rework", "Implement"],
        "objects": [
            "Room schema for task and project entities",
            "local cache invalidation and refresh policy",
            "offline-first synchronization pipeline",
            "DAO query strategy for dashboard metrics",
            "database migration plan for version upgrades",
        ],
        "context": [
            "for Android app data layer",
            "using Kotlin and Room",
            "with repository mediation between API and local DB",
            "for a Compose-first architecture",
            "in an app with large dataset pagination",
        ],
        "constraints": [
            "define migration tests for schema changes",
            "include conflict resolution strategy",
            "enforce transactional writes where needed",
            "include performance checks for heavy queries",
            "document rollback behavior for failed sync",
        ],
    },
    "ui_compose": {
        "verbs": ["Implement", "Redesign", "Build", "Polish", "Launch"],
        "objects": [
            "Compose dashboard screen with filtering",
            "settings module with nested navigation",
            "profile and account management screens",
            "search experience with debounced queries",
            "multi-step checkout UI flow",
        ],
        "context": [
            "using Jetpack Compose and Material 3",
            "with Navigation Compose and ViewModel",
            "for tablet and phone form factors",
            "with dark/light theme support",
            "in a modular Android app",
        ],
        "constraints": [
            "include accessibility and talkback support",
            "define UI state model for loading/empty/error",
            "add screenshot or golden test coverage",
            "ensure back stack behavior is deterministic",
            "include performance considerations for recomposition",
        ],
    },
    "testing_quality": {
        "verbs": ["Increase", "Enforce", "Improve", "Stabilize", "Automate"],
        "objects": [
            "unit and instrumentation coverage for critical flows",
            "lint and static analysis quality gates",
            "flaky test triage and stabilization plan",
            "CI quality gate for Android modules",
            "release readiness checks for core user journeys",
        ],
        "context": [
            "for a Kotlin Android app",
            "in a multi-module Android project",
            "for a Compose-heavy codebase",
            "for a legacy module under refactor",
            "with Gradle-based CI pipelines",
        ],
        "constraints": [
            "include coverage thresholds and enforcement",
            "include failure diagnostics and reporting",
            "include deterministic test data setup",
            "include lint baseline cleanup strategy",
            "include rollout safety checks",
        ],
    },
}

SEVERITIES = ["low", "medium", "high"]
PRIORITIES = ["p2", "p1", "p0"]


def build_prompt(bucket: Dict[str, List[str]], rng: random.Random) -> str:
    return (
        f"{rng.choice(bucket['verbs'])} {rng.choice(bucket['objects'])} "
        f"{rng.choice(bucket['context'])}; {rng.choice(bucket['constraints'])}."
    )


def build_rows(total: int, seed: int) -> List[dict]:
    rng = random.Random(seed)
    planner = RuleBasedAndroidPlanner()
    category_names = list(CATEGORIES.keys())

    rows: List[dict] = []
    for idx in range(total):
        category = category_names[idx % len(category_names)]
        prompt = build_prompt(CATEGORIES[category], rng)
        plan = planner.plan(prompt)
        plan_dict = plan.model_dump()
        plan_dict["confidence"] = round(max(plan_dict["confidence"], 0.82), 3)
        rows.append(
            {
                "id": f"G-{idx + 1:04d}",
                "category": category,
                "prompt": prompt,
                "is_android_related": True,
                "difficulty": rng.choice(SEVERITIES),
                "priority": rng.choice(PRIORITIES),
                "task_plan": plan_dict,
                "review_status": "seeded_needs_human_review",
                "review_notes": "",
            }
        )
    return rows


def write_annotation_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "id",
        "category",
        "prompt",
        "difficulty",
        "priority",
        "review_status",
        "review_notes",
        "approved",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "id": row["id"],
                    "category": row["category"],
                    "prompt": row["prompt"],
                    "difficulty": row["difficulty"],
                    "priority": row["priority"],
                    "review_status": row["review_status"],
                    "review_notes": "",
                    "approved": "no",
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create 200-example Android gold seed dataset.")
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default="data/gold")
    args = parser.parse_args()

    rows = build_rows(total=args.count, seed=args.seed)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(out_dir / "android_gold_seed_v1.jsonl", rows)
    write_annotation_csv(out_dir / "android_gold_annotation_template_v1.csv", rows)

    print(f"Wrote {len(rows)} curated seed examples to {out_dir / 'android_gold_seed_v1.jsonl'}")
    print(f"Wrote annotation template to {out_dir / 'android_gold_annotation_template_v1.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
