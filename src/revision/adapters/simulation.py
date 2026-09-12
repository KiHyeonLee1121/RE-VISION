"""Deterministic workflow fixtures, explicitly NOT trained AI or optical simulation."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from revision.domain import Frame, LightAction, Prediction

SCENARIOS = {
    "clean": {"front": 0.04, "rear": 0.07, "left": 0.08, "right_dim": 0.06},
    "scratch": {"front": 0.52, "rear": 0.96, "left": 0.81, "right_dim": 0.65},
    "uncertain": {"front": 0.48, "rear": 0.57, "left": 0.53, "right_dim": 0.49},
    "glare": {"front": 0.95, "rear": 0.06, "left": 0.07, "right_dim": 0.05},
}


class MockLighting:
    def __init__(self) -> None:
        self.active: str | None = None

    def apply(self, action: LightAction) -> None:
        self.active = action.id

    def off(self) -> None:
        self.active = None

    def close(self) -> None:
        self.off()


class DemoCamera:
    def __init__(self, scenario: str) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown demo scenario: {scenario}")
        self.scenario = scenario

    def capture(self, action: LightAction, output_dir: Path) -> Frame:
        frame_id = uuid4().hex
        path = output_dir / f"{frame_id}.pgm"
        size = 64
        pixels = bytes(
            220 if self.scenario == "scratch" and x == 30 else 100 + (x + y) % 20
            for y in range(size)
            for x in range(size)
        )
        path.write_bytes(f"P5\n{size} {size}\n255\n".encode() + pixels)
        return Frame(
            frame_id,
            action.id,
            str(path),
            size,
            size,
            datetime.now(UTC).isoformat(),
            saturation_ratio=0.6 if self.scenario == "glare" and action.id == "front" else 0,
        )

    def close(self) -> None:
        pass


class DemoPredictor:
    def __init__(self, scenario: str) -> None:
        self.scores = SCENARIOS[scenario]

    def predict(self, frame: Frame) -> Prediction:
        if frame.action_id not in self.scores:
            raise ValueError("demo scenarios require the default light action ids")
        return Prediction(self.scores[frame.action_id], "demo-fixture-v1")


class ReplayCamera:
    """Replay one fixed part under recorded light conditions (no hardware commands)."""

    def __init__(self, manifest: Path) -> None:
        self.root = manifest.resolve().parent
        self.entries = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(self.entries, dict) or not self.entries:
            raise ValueError("replay manifest must map action ids to frame records")

    def capture(self, action: LightAction, output_dir: Path) -> Frame:
        row = self.entries[action.id]
        source = (self.root / row["image_path"]).resolve()
        frame_id = uuid4().hex
        target = output_dir / f"{frame_id}{source.suffix}"
        shutil.copyfile(source, target)
        # Recorded quality fields belong to the saved capture, not prediction confidence.
        return Frame(
            frame_id,
            action.id,
            str(target),
            row["width"],
            row["height"],
            row["captured_at"],
            row.get("saturation_ratio", 0),
            row.get("dark_ratio", 0),
        )

    def close(self) -> None:
        pass


class ReplayPredictor:
    def __init__(self, camera: ReplayCamera) -> None:
        self.entries = camera.entries

    def predict(self, frame: Frame) -> Prediction:
        return Prediction(self.entries[frame.action_id]["defect_score"], "recorded-score-replay")
