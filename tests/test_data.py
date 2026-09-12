import json

import pytest

from revision.data.manifest import load_dataset, split_dataset
from revision.data.metrics import evaluate


def test_split_keeps_part_and_session_connected_components_together():
    rows = [
        {"part_id": "a", "session_id": "s1"},
        {"part_id": "a", "session_id": "s2"},
        {"part_id": "b", "session_id": "s2"},
        {"part_id": "c", "session_id": "s3"},
        {"part_id": "d", "session_id": "s4"},
        {"part_id": "e", "session_id": "s4"},
    ]
    splits = split_dataset(rows)
    assert splits == split_dataset(rows)
    assert all(splits.values())
    for key in ("part_id", "session_id"):
        members = [{r[key] for r in split} for split in splits.values()]
        assert not members[0] & members[1]
        assert not members[0] & members[2]
        assert not members[1] & members[2]


def test_too_few_independent_groups_rejected():
    with pytest.raises(ValueError, match="independent"):
        split_dataset(
            [{"part_id": "a", "session_id": "one"}, {"part_id": "b", "session_id": "one"}]
        )


def test_duplicate_bytes_and_wrong_labels_rejected(tmp_path):
    (tmp_path / "a.pgm").write_bytes(b"P5\n1 1\n255\n\x80")
    path = tmp_path / "manifest.jsonl"
    row = {
        "sample_id": "a",
        "part_id": "a",
        "session_id": "one",
        "light_id": "front",
        "image_path": "a.pgm",
        "label": "clean",
    }
    path.write_text(json.dumps(row) + "\n" + json.dumps({**row, "sample_id": "b"}))
    with pytest.raises(ValueError, match="duplicate image"):
        load_dataset(path)
    path.write_text(json.dumps({**row, "label": "unknown"}))
    with pytest.raises(ValueError, match="label"):
        load_dataset(path)


def test_metrics_include_review_and_error_in_denominators():
    rows = [
        {
            "part_id": "a",
            "label": "defective",
            "verdict": "PASS",
            "duration_ms": 10,
            "view_count": 1,
        },
        {
            "part_id": "b",
            "label": "defective",
            "verdict": "REVIEW",
            "duration_ms": 30,
            "view_count": 3,
        },
        {"part_id": "c", "label": "clean", "verdict": "ERROR", "duration_ms": 20, "view_count": 1},
    ]
    metrics = evaluate(rows)
    assert metrics["automatic_coverage"] == 1 / 3
    assert metrics["false_pass_rate"] == 0.5
    assert metrics["defect_recall"] == 0
    assert metrics["latency_ms"]["p50"] == 20
