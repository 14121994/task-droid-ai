#!/usr/bin/env python3
"""Build mode-aware SFT rows and fine-tune taskdroid on openai/gpt-oss-20b."""

from __future__ import annotations

import argparse
from pathlib import Path

from android_planner.prompting import INTELLIGENCE_LEVELS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fine-tune taskdroid planner on openai/gpt-oss-20b.")
    parser.add_argument("--model-name", type=str, default="openai/gpt-oss-20b")
    parser.add_argument("--input-file", type=str, default="data/raw/prompt_plans.jsonl")
    parser.add_argument("--processed-dir", type=str, default="data/processed/gpt_oss_20b")
    parser.add_argument("--output-dir", type=str, default="data/models/taskdroid-gpt-oss-20b-lora")
    parser.add_argument(
        "--intelligence-levels",
        nargs="+",
        choices=INTELLIGENCE_LEVELS,
        default=list(INTELLIGENCE_LEVELS),
    )
    parser.add_argument("--android-only", action="store_true")
    parser.add_argument("--skip-build-dataset", action="store_true")
    parser.add_argument("--max-seq-length", type=int, default=4096)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--cache-dir", type=str, default="data/cache/huggingface")
    parser.add_argument("--no-bf16", action="store_true")
    args = parser.parse_args(argv)

    processed_dir = Path(args.processed_dir)
    if not args.skip_build_dataset:
        import build_sft_dataset

        build_args = [
            "--input-file",
            args.input_file,
            "--output-dir",
            str(processed_dir),
            "--expand-intelligence-levels",
            "--intelligence-levels",
            *args.intelligence_levels,
        ]
        if args.android_only:
            build_args.append("--android-only")
        build_sft_dataset.main(build_args)

    import train_lora_planner

    train_args = [
        "--model-name",
        args.model_name,
        "--train-file",
        str(processed_dir / "sft_train.jsonl"),
        "--val-file",
        str(processed_dir / "sft_val.jsonl"),
        "--output-dir",
        args.output_dir,
        "--max-seq-length",
        str(args.max_seq_length),
        "--batch-size",
        str(args.batch_size),
        "--grad-accum",
        str(args.grad_accum),
        "--epochs",
        str(args.epochs),
        "--learning-rate",
        str(args.learning_rate),
        "--cache-dir",
        args.cache_dir,
    ]
    if not args.no_bf16:
        train_args.append("--use-bf16")
    return train_lora_planner.main(train_args)


if __name__ == "__main__":
    raise SystemExit(main())
