#!/usr/bin/env python3
"""Run end-to-end local pipeline for Android planner project."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List


def _run(command: List[str], env: dict) -> None:
    print(f"\n[RUN] {' '.join(command)}")
    subprocess.run(command, check=True, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full Android planner pipeline.")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-lora", action="store_true")
    parser.add_argument("--python", type=str, default=sys.executable)
    args = parser.parse_args()

    python = args.python
    root = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    src_path = str(root / "src")
    env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else src_path

    if not args.skip_tests:
        _run([python, "-m", "pytest"], env=env)

    _run([python, "scripts/generate_seed_dataset.py"], env=env)
    _run([python, "scripts/train_baseline_classifier.py"], env=env)
    _run([python, "scripts/evaluate_baseline_classifier.py"], env=env)
    _run([python, "scripts/train_torch_classifier.py"], env=env)
    _run([python, "scripts/build_sft_dataset.py", "--android-only"], env=env)
    _run([python, "scripts/evaluate_planner_outputs.py"], env=env)

    if not args.skip_lora:
        _run([python, "scripts/train_lora_planner.py"], env=env)

    print(f"\nPipeline completed successfully in {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
