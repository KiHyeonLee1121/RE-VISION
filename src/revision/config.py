"""TOML configuration. Paths are relative to the config file, not the shell cwd."""

import json
import tomllib
from dataclasses import asdict, dataclass, field
from math import isfinite
from pathlib import Path

from revision.domain import LightAction


@dataclass(frozen=True)
class InspectionSettings:
    max_views: int = 4
    budget_ms: float = 5000
    pass_threshold: float = 0.15
    fail_threshold: float = 0.85
    min_pass_views: int = 1
    max_saturation_ratio: float = 0.25
    max_dark_ratio: float = 0.80

    def __post_init__(self) -> None:
        if not 1 <= self.min_pass_views <= self.max_views <= 64:
            raise ValueError("require 1 <= min_pass_views <= max_views <= 64")
        if not isfinite(self.budget_ms) or self.budget_ms <= 0:
            raise ValueError("budget_ms must be finite and positive")
        if not 0 <= self.pass_threshold < self.fail_threshold <= 1:
            raise ValueError("require 0 <= pass_threshold < fail_threshold <= 1")
        for value in (self.max_saturation_ratio, self.max_dark_ratio):
            if not isfinite(value) or not 0 <= value <= 1:
                raise ValueError("invalid image quality threshold")


@dataclass(frozen=True)
class CameraSettings:
    device: int = 0
    width: int = 1280
    height: int = 720
    flush_frames: int = 3

    def __post_init__(self) -> None:
        if min(self.width, self.height) < 1 or not 1 <= self.flush_frames <= 30:
            raise ValueError("invalid camera size or flush_frames")


@dataclass(frozen=True)
class SerialSettings:
    port: str = ""
    baudrate: int = 115200
    timeout_s: float = 1.0

    def __post_init__(self) -> None:
        if self.baudrate <= 0 or not isfinite(self.timeout_s) or not 0 < self.timeout_s <= 10:
            raise ValueError("invalid serial baudrate or timeout")


@dataclass(frozen=True)
class AppConfig:
    mode: str = "demo"
    output_dir: Path = Path("outputs")
    scenario: str = "scratch"
    replay_manifest: Path | None = None
    model_manifest: Path | None = None
    inspection: InspectionSettings = field(default_factory=InspectionSettings)
    camera: CameraSettings = field(default_factory=CameraSettings)
    serial: SerialSettings = field(default_factory=SerialSettings)
    actions: tuple[LightAction, ...] = field(
        default_factory=lambda: (
            LightAction("front", 0, 0, 0.7, 0),
            LightAction("rear", 1, 180, 0.7, 0),
            LightAction("left", 2, 90, 0.7, 0),
            LightAction("right_dim", 3, 270, 0.35, 0),
        )
    )

    def __post_init__(self) -> None:
        if self.mode not in {"demo", "replay", "live"}:
            raise ValueError("mode must be demo, replay, or live")
        if not self.actions or len({a.id for a in self.actions}) != len(self.actions):
            raise ValueError("light actions must be nonempty with unique ids")
        if self.inspection.min_pass_views > len(self.actions):
            raise ValueError("not enough light actions for min_pass_views")
        if self.mode == "replay" and self.replay_manifest is None:
            raise ValueError("replay mode requires replay_manifest")
        if self.mode == "live" and (self.model_manifest is None or not self.serial.port):
            raise ValueError("live mode requires a model manifest and serial port")

    def snapshot(self) -> dict:
        return json.loads(json.dumps(asdict(self), default=str))


def load_config(path: Path) -> AppConfig:
    path = path.resolve()
    with path.open("rb") as file:
        raw = tomllib.load(file)
    raw.setdefault("output_dir", "outputs")
    for name in ("output_dir", "replay_manifest", "model_manifest"):
        if name in raw:
            raw[name] = (path.parent / raw[name]).resolve()
    raw["inspection"] = InspectionSettings(**raw.get("inspection", {}))
    raw["camera"] = CameraSettings(**raw.get("camera", {}))
    raw["serial"] = SerialSettings(**raw.get("serial", {}))
    if "actions" in raw:
        raw["actions"] = tuple(LightAction(**a) for a in raw["actions"])
    return AppConfig(**raw)  # Unknown keys raise rather than silently changing behavior.
