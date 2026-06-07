import json

import pytest

from android_planner.cli import main


def test_cli_accepts_intelligence_level_and_prints_plan(capsys):
    exit_code = main(
        [
            "--prompt",
            "Build Android Compose settings screen with tests.",
            "--intelligence-level",
            "xhigh",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["is_android_related"] is True
    assert len(payload["implementation_tasks"]) > 4


def test_cli_writes_output_file(tmp_path):
    output_path = tmp_path / "plan.json"
    exit_code = main(
        [
            "--prompt",
            "Build Android Compose settings screen with tests.",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["plan_category"] == "implementation"


def test_cli_reads_prompt_from_input_file(tmp_path, capsys):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Build Android Room cache with tests.", encoding="utf-8")

    exit_code = main(["--input-file", str(prompt_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["is_android_related"] is True


def test_cli_rejects_missing_prompt_or_input_file():
    with pytest.raises(ValueError, match="Either --prompt or --input-file"):
        main([])
