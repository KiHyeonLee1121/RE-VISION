import json
import zipfile
from pathlib import Path

import pytest

from revision.data.staging import dataset_signature, prepare_splits, stage_dataset
from revision.ml.artifacts import atomic_json, latest_checkpoint, sha256_file, verified_copy


def make_dataset(root: Path):
    root.mkdir()
    rows = []
    for session in range(5):
        for defect in range(2):
            sample = f"s{session}-{defect}"
            image = root / f"{sample}.pgm"
            image.write_bytes(b"P5\n2 1\n255\n" + bytes([50 + session, 100 + defect]))
            rows.append(
                {
                    "sample_id": sample,
                    "part_id": sample,
                    "session_id": f"s{session}",
                    "light_id": "front",
                    "image_path": image.name,
                    "label": "defective" if defect else "clean",
                }
            )
    (root / "manifest.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    return rows


@pytest.mark.parametrize("archive", [False, True])
def test_stage_copies_without_modifying_drive_source(tmp_path, archive):
    source = tmp_path / "drive-dataset"
    make_dataset(source)
    manifest_bytes = (source / "manifest.jsonl").read_bytes()
    selected = source
    if archive:
        selected = tmp_path / "dataset.zip"
        with zipfile.ZipFile(selected, "w") as bundle:
            for item in source.iterdir():
                bundle.write(item, item.name)
    staged = stage_dataset(selected, tmp_path / "cache")
    summary = prepare_splits(staged, tmp_path / "splits")
    assert all(
        row["clean_images"] and row["defective_images"] for row in summary["splits"].values()
    )
    assert (source / "manifest.jsonl").read_bytes() == manifest_bytes
    assert str(tmp_path) not in json.dumps(summary)
    assert staged != source / "manifest.jsonl"


def test_signature_survives_runtime_path_change():
    original = {
        "train": [{"sample_id": "a", "image_path": "/old/a", "sha256": "hash", "label": "clean"}]
    }
    copied = {"train": [{**original["train"][0], "image_path": "/new/a"}]}
    assert dataset_signature(original) == dataset_signature(copied)
    copied["train"][0]["label"] = "defective"
    assert dataset_signature(original) != dataset_signature(copied)


@pytest.mark.parametrize("entry", ["../outside.txt", "/absolute.txt", "folder\\..\\outside.txt"])
def test_zip_path_traversal_rejected(tmp_path, entry):
    source = tmp_path / "bad.zip"
    with zipfile.ZipFile(source, "w") as bundle:
        bundle.writestr(entry, "bad")
    with pytest.raises(ValueError, match="unsafe"):
        stage_dataset(source, tmp_path / "cache")
    assert list((tmp_path / "cache").iterdir()) == []


def test_outside_manifest_reference_rejected(tmp_path):
    source = tmp_path / "data"
    rows = make_dataset(source)
    rows[0]["image_path"] = "../outside.pgm"
    (source / "manifest.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    with pytest.raises(ValueError, match="inside dataset"):
        stage_dataset(source, tmp_path / "cache")


def test_verified_copy_and_checkpoint_corruption(tmp_path):
    source = tmp_path / "local.pt"
    source.write_bytes(b"checkpoint-data")
    run = tmp_path / "drive-run"
    target = run / "checkpoints" / "epoch1.pt"
    digest = verified_copy(source, target)
    atomic_json(run / "latest.json", {"path": "checkpoints/epoch1.pt", "sha256": digest})
    assert latest_checkpoint(run) == target
    assert sha256_file(source) == digest
    target.write_bytes(b"incomplete")
    with pytest.raises(ValueError, match="checksum"):
        latest_checkpoint(run)
    assert source.read_bytes() == b"checkpoint-data"
