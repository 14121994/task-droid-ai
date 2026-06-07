#!/usr/bin/env python3
"""Check project coverage thresholds beyond coverage.py's built-in line gate."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


def _percent(covered: int, total: int) -> float:
    return 100.0 if total == 0 else covered / total * 100.0


def _body_lines(node: ast.AST) -> set[int]:
    body = getattr(node, "body", [])
    if not body:
        return {getattr(node, "lineno", 0)}
    lines: set[int] = set()
    for child in body:
        start = getattr(child, "lineno", None)
        end = getattr(child, "end_lineno", start)
        if start is not None and end is not None:
            lines.update(range(start, end + 1))
    return lines


def _object_coverage(report: dict[str, Any], source_root: Path) -> dict[str, float | int]:
    covered_lines_by_file = {
        Path(filename): set(file_report.get("executed_lines", []))
        for filename, file_report in report.get("files", {}).items()
    }

    method_total = method_covered = 0
    class_total = class_covered = 0

    for source_path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        report_key = source_path.as_posix()
        covered_lines = covered_lines_by_file.get(Path(report_key), set())
        class_stack: list[ast.ClassDef] = []

        class Visitor(ast.NodeVisitor):
            def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
                nonlocal class_total, class_covered
                class_total += 1
                if node.lineno in covered_lines or covered_lines.intersection(_body_lines(node)):
                    class_covered += 1
                class_stack.append(node)
                self.generic_visit(node)
                class_stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
                nonlocal method_total, method_covered
                if class_stack:
                    method_total += 1
                    if covered_lines.intersection(_body_lines(node)):
                        method_covered += 1
                self.generic_visit(node)

            visit_AsyncFunctionDef = visit_FunctionDef

        Visitor().visit(tree)

    return {
        "method_covered": method_covered,
        "method_total": method_total,
        "method_percent": _percent(method_covered, method_total),
        "class_covered": class_covered,
        "class_total": class_total,
        "class_percent": _percent(class_covered, class_total),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check line, branch, method, and class coverage thresholds.")
    parser.add_argument("--coverage-json", default="coverage.json")
    parser.add_argument("--source-root", default="src/android_planner")
    parser.add_argument("--line-threshold", type=float, default=90.0)
    parser.add_argument("--branch-threshold", type=float, default=90.0)
    parser.add_argument("--method-threshold", type=float, default=90.0)
    parser.add_argument("--class-threshold", type=float, default=90.0)
    args = parser.parse_args()

    report = json.loads(Path(args.coverage_json).read_text(encoding="utf-8"))
    totals = report["totals"]
    object_totals = _object_coverage(report, Path(args.source_root))
    metrics = {
        "line": float(totals["percent_statements_covered"]),
        "branch": float(totals["percent_branches_covered"]),
        "method": float(object_totals["method_percent"]),
        "class": float(object_totals["class_percent"]),
    }
    thresholds = {
        "line": args.line_threshold,
        "branch": args.branch_threshold,
        "method": args.method_threshold,
        "class": args.class_threshold,
    }

    failures = [
        f"{name} coverage {metrics[name]:.2f}% is below required {thresholds[name]:.2f}%"
        for name in metrics
        if metrics[name] < thresholds[name]
    ]

    print(
        json.dumps(
            {
                "coverage": {name: round(value, 2) for name, value in metrics.items()},
                "thresholds": thresholds,
                "method_covered": object_totals["method_covered"],
                "method_total": object_totals["method_total"],
                "class_covered": object_totals["class_covered"],
                "class_total": object_totals["class_total"],
                "passed": not failures,
                "failures": failures,
            },
            indent=2,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
