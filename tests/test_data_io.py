import json

import pytest

from android_planner.data_io import read_jsonl, split_rows, write_jsonl


def test_read_jsonl_returns_empty_for_missing_file(tmp_path):
    assert read_jsonl(tmp_path / "missing.jsonl") == []


def test_write_and_read_jsonl_round_trip_skips_blank_lines(tmp_path):
    path = tmp_path / "nested" / "rows.jsonl"
    rows = [{"id": "1", "prompt": "Build Android app"}, {"id": "2", "prompt": "Fix crash"}]

    write_jsonl(path, rows)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
        handle.write(json.dumps({"id": "3", "prompt": "Add tests"}) + "\n")

    assert read_jsonl(path) == rows + [{"id": "3", "prompt": "Add tests"}]


def test_split_rows_is_deterministic_and_complete():
    rows = [{"id": str(index)} for index in range(10)]

    first = split_rows(rows, train_ratio=0.6, val_ratio=0.2, seed=7)
    second = split_rows(rows, train_ratio=0.6, val_ratio=0.2, seed=7)

    assert first == second
    assert [len(part) for part in first] == [6, 2, 2]
    assert sorted(row["id"] for part in first for row in part) == [str(index) for index in range(10)]


@pytest.mark.parametrize(
    ("train_ratio", "val_ratio"),
    [
        (0.0, 0.2),
        (0.7, 0.0),
        (0.8, 0.2),
    ],
)
def test_split_rows_rejects_invalid_ratios(train_ratio, val_ratio):
    with pytest.raises(ValueError, match="Invalid split ratios"):
        split_rows([{"id": "1"}], train_ratio=train_ratio, val_ratio=val_ratio)
