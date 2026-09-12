"""Verified copies and versioned checkpoint files for mounted Drive or local storage."""

import hashlib
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temp.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
        )
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def verified_copy(source: Path, target: Path) -> str:
    """Write temporary bytes, verify checksum, then replace the destination.

    A successful mounted-file readback is not a guarantee of Drive server-side sync.
    Never move the only source copy off the training runtime.
    """
    if source.resolve() == target.resolve():
        return sha256_file(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + "." + uuid4().hex + ".tmp")
    try:
        shutil.copyfile(source, temp)
        digest = sha256_file(source)
        if sha256_file(temp) != digest:
            raise OSError("artifact copy checksum mismatch")
        os.replace(temp, target)
        return digest
    finally:
        temp.unlink(missing_ok=True)


def save_checkpoint(payload: dict, local_dir: Path, drive_run: Path) -> Path:
    """Commit a versioned checkpoint, then update a small pointer; retain old checkpoints."""
    import torch

    local_dir.mkdir(parents=True, exist_ok=True)
    filename = f"epoch-{payload['epoch']:04d}-{uuid4().hex[:8]}.pt"
    local_path = local_dir / filename
    torch.save(payload, local_path)
    target = drive_run / "checkpoints" / filename
    digest = verified_copy(local_path, target)
    atomic_json(
        drive_run / "latest.json",
        {
            "schema_version": 1,
            "path": "checkpoints/" + filename,
            "sha256": digest,
            "epoch": payload["epoch"],
        },
    )
    return target


def latest_checkpoint(drive_run: Path) -> Path:
    pointer = json.loads((drive_run / "latest.json").read_text(encoding="utf-8"))
    path = (drive_run / pointer["path"]).resolve()
    if not path.is_relative_to((drive_run / "checkpoints").resolve()):
        raise ValueError("checkpoint pointer escapes the checkpoint directory")
    if sha256_file(path) != pointer["sha256"]:
        raise ValueError("checkpoint checksum mismatch; select a previous verified checkpoint")
    return path
