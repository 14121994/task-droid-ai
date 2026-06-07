"""Command-line entrypoint for Android prompt planning."""

from __future__ import annotations

import argparse
from pathlib import Path

from .rule_planner import RuleBasedAndroidPlanner


def _read_prompt(args: argparse.Namespace) -> str:
    if args.prompt:
        return args.prompt
    if args.input_file:
        return Path(args.input_file).read_text(encoding="utf-8")
    raise ValueError("Either --prompt or --input-file must be provided.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Android prompt-to-implementation task planner")
    parser.add_argument("--prompt", type=str, help="Raw user prompt")
    parser.add_argument("--input-file", type=str, help="Path to a file containing the user prompt")
    parser.add_argument("--output", type=str, help="Optional path to write JSON output")
    parser.add_argument(
        "--intelligence-level",
        choices=["low", "medium", "high", "xhigh"],
        default="medium",
        help="Planner depth to use for rule planning.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    prompt = _read_prompt(args)

    planner = RuleBasedAndroidPlanner()
    plan = planner.plan(prompt, intelligence_level=args.intelligence_level)
    output_json = plan.to_pretty_json()

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output_json + "\n", encoding="utf-8")
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
