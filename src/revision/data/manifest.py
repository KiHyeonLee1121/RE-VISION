import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path


def load_dataset(path: Path) -> list[dict]:
    """Validate a JSONL manifest and return rows with absolute image paths.

    Same physical part MUST retain the same part_id across sessions and lights.
    Labels: clean / defective. Missing defect localization is allowed for classification.
    """
    rows, ids, hashes = [], set(), {}
    part_labels: dict[str, str] = {}
    required = {"sample_id", "part_id", "session_id", "light_id", "image_path", "label"}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not required <= row.keys() or any(
            not isinstance(row[k], str) or not row[k] for k in required
        ):
            raise ValueError(f"line {line_number}: missing or invalid required field")
        if row["sample_id"] in ids or row["label"] not in {"clean", "defective"}:
            raise ValueError(f"line {line_number}: duplicate sample_id or unknown label")
        ids.add(row["sample_id"])
        if part_labels.setdefault(row["part_id"], row["label"]) != row["label"]:
            raise ValueError(
                "one physical part has inconsistent labels; model physical states explicitly"
            )
        image = (path.resolve().parent / row["image_path"]).resolve()
        if not image.is_file():
            raise ValueError(f"line {line_number}: image not found")
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        if digest in hashes:
            raise ValueError(f"duplicate image bytes: {hashes[digest]} and {row['sample_id']}")
        hashes[digest] = row["sample_id"]
        if "sha256" in row and row["sha256"] != digest:
            raise ValueError(f"line {line_number}: SHA256 mismatch")
        rows.append({**row, "image_path": str(image), "sha256": digest})
    if not rows:
        raise ValueError("empty dataset")
    return rows


def split_dataset(rows: list[dict], seed: int = 42) -> dict[str, list[dict]]:
    """Connected components prevent leakage through EITHER shared part OR shared session.

    60/20/20 approximate by connected group count; class stratification is not guaranteed.
    Reject fewer than three independent groups instead of falling back to image-level splits.
    """
    parent: dict[str, str] = {}

    def root(key: str) -> str:
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for row in rows:
        a, b = root("part:" + row["part_id"]), root("session:" + row["session_id"])
        parent[a] = b
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[root("part:" + row["part_id"])].append(row)
    keys = sorted(groups)
    if len(keys) < 3:
        raise ValueError("need at least 3 independent part/session groups; collect more sessions")
    random.Random(seed).shuffle(keys)
    n_train = min(len(keys) - 2, max(1, int(len(keys) * 0.6)))
    n_val = min(len(keys) - n_train - 1, max(1, int(len(keys) * 0.2)))
    buckets = {
        "train": keys[:n_train],
        "val": keys[n_train : n_train + n_val],
        "test": keys[n_train + n_val :],
    }
    return {
        name: [row for key in members for row in groups[key]] for name, members in buckets.items()
    }


def write_splits(splits: dict[str, list[dict]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in splits.items():
        (output / f"{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
