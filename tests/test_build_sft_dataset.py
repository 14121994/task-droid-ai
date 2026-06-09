import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_sft_dataset import build_chat_rows, to_chat_row  # noqa: E402


def _row() -> dict:
    return {
        "id": "A-1",
        "prompt": "Build Android passkey sign-in with recovery fallback.",
        "is_android_related": True,
        "task_plan": {
            "is_android_related": True,
            "confidence": 0.9,
            "feature_summary": "Plan passkey sign-in",
            "files_or_modules": ["AuthViewModel.kt"],
            "implementation_tasks": [
                {
                    "id": "T1",
                    "title": "Define auth state",
                    "description": "Model passkey states.",
                    "layer": "domain",
                    "estimated_effort": "M",
                    "dependencies": [],
                }
            ],
            "acceptance_checks": ["Unit tests cover passkey success"],
            "risks": ["Credential provider differences"],
            "questions_for_user": [],
        },
    }


def test_to_chat_row_uses_shared_mode_prompt_and_normalizes_schema():
    row = to_chat_row(_row())

    assert row["id"] == "A-1"
    assert row["intelligence_level"] == "medium"
    assert row["messages"][0]["role"] == "system"
    assert "Planner intelligence_level: medium" in row["messages"][0]["content"]

    target = json.loads(row["messages"][-1]["content"])
    assert target["plan_quality_score"] == 0.0
    assert target["plan_category"] == "implementation"


def test_build_chat_rows_expands_selected_intelligence_levels():
    rows = build_chat_rows([_row()], expand_intelligence_levels=True, intelligence_levels=["low", "xhigh"])

    assert [row["id"] for row in rows] == ["A-1-low", "A-1-xhigh"]
    assert [row["intelligence_level"] for row in rows] == ["low", "xhigh"]
    assert "Planner intelligence_level: low" in rows[0]["messages"][0]["content"]
    assert "Planner intelligence_level: xhigh" in rows[1]["messages"][0]["content"]

    low_target = json.loads(rows[0]["messages"][-1]["content"])
    xhigh_target = json.loads(rows[1]["messages"][-1]["content"])
    assert len(low_target["implementation_tasks"]) < len(xhigh_target["implementation_tasks"])
