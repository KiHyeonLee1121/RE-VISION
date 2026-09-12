"""Copy a portable Drive folder or ZIP into a runtime cache without changing the source."""

import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from revision.data.manifest import load_dataset, split_dataset, write_splits
from revision.ml.artifacts import atomic_json


def dataset_signature(splits: dict[str, list[dict]]) -> str:
    import hashlib

    # Runtime and Drive absolute paths may change; content, labels and membership may not.
    canonical = {
        name: sorted(
            [{k: v for k, v in row.items() if k != "image_path"} for row in rows],
            key=lambda row: row["sample_id"],
        )
        for name, rows in splits.items()
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def _extract_zip(archive: Path, target: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if sum(item.file_size for item in entries) > shutil.disk_usage(target).free * 0.9:
            raise OSError("not enough local disk space for the uncompressed dataset")
        seen = set()
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if (
                name.is_absolute()
                or ".." in name.parts
                or "\\" in entry.filename
                or ":" in entry.filename
                or stat.S_ISLNK(entry.external_attr >> 16)
                or entry.filename in seen
            ):
                raise ValueError("ZIP contains unsafe or duplicate paths")
            seen.add(entry.filename)
        bundle.extractall(target)


def stage_dataset(source: Path, cache_root: Path) -> Path:
    """Require manifest.jsonl at the source root, with relative image paths inside it."""
    source, cache_root = source.resolve(), cache_root.resolve()
    if cache_root == source or cache_root.is_relative_to(source):
        raise ValueError("runtime cache must be outside the source dataset")
    cache_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="dataset-", dir=cache_root))
    target = work / "data"
    try:
        if source.is_dir():
            members = list(source.rglob("*"))
            if any(path.is_symlink() for path in members):
                raise ValueError("dataset folder must not contain symlinks")
            if (
                sum(path.stat().st_size for path in members if path.is_file())
                > shutil.disk_usage(work).free * 0.9
            ):
                raise OSError("not enough local disk space for dataset copy")
            shutil.copytree(source, target)
        elif source.is_file() and source.suffix.lower() == ".zip":
            archive = work / "source.zip"
            shutil.copyfile(source, archive)
            target.mkdir()
            _extract_zip(archive, target)
            archive.unlink()
        else:
            raise ValueError("dataset source must be a directory or .zip")
        manifest = target / "manifest.jsonl"
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.strip():
                relative = Path(json.loads(line)["image_path"])
                if relative.is_absolute() or not (target / relative).resolve().is_relative_to(
                    target
                ):
                    raise ValueError(
                        "Drive manifest image_path must be relative and inside dataset"
                    )
        load_dataset(manifest)
        return manifest
    except BaseException:
        shutil.rmtree(work)
        raise


def prepare_splits(manifest: Path, output: Path, seed: int = 42) -> dict:
    rows = load_dataset(manifest)
    splits = split_dataset(rows, seed)
    for name in ("train", "val"):
        if {r["label"] for r in splits[name]} != {"clean", "defective"}:
            raise ValueError(
                f"{name} must contain both classes; collect balanced independent sessions"
            )
    write_splits(splits, output)
    summary = {
        "schema_version": 1,
        "seed": seed,
        "dataset_signature": dataset_signature(splits),
        "splits": {
            name: {
                "sample_ids": [r["sample_id"] for r in values],
                "parts": len({r["part_id"] for r in values}),
                "sessions": len({r["session_id"] for r in values}),
                "images": len(values),
                "clean_images": sum(r["label"] == "clean" for r in values),
                "defective_images": sum(r["label"] == "defective" for r in values),
            }
            for name, values in splits.items()
        },
    }
    atomic_json(output / "split-summary.json", summary)
    return summary
