"""Shared contracts. Coordinates refer to the ORIGINAL captured image, in pixels."""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from math import isfinite


def unit_interval(value: float, name: str) -> None:
    if not isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be finite and in [0, 1]")


class Verdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"  # Insufficient evidence; do not silently release the part.
    ERROR = "ERROR"  # Device, model, or persistence failure.


@dataclass(frozen=True)
class LightAction:
    id: str
    channel: int
    direction_deg: float
    intensity: float
    settle_ms: int = 50

    def __post_init__(self) -> None:
        if not self.id or not 0 <= self.channel <= 255:
            raise ValueError("light action requires an id and channel in [0, 255]")
        unit_interval(self.intensity, "intensity")
        if self.intensity == 0 or not isfinite(self.direction_deg) or self.settle_ms < 0:
            raise ValueError("invalid direction, intensity or settling time")


@dataclass(frozen=True)
class Frame:
    id: str
    action_id: str
    path: str
    width: int
    height: int
    captured_at: str
    saturation_ratio: float = 0.0
    dark_ratio: float = 0.0

    def __post_init__(self) -> None:
        if self.width < 1 or self.height < 1:
            raise ValueError("frame dimensions must be positive")
        unit_interval(self.saturation_ratio, "saturation_ratio")
        unit_interval(self.dark_ratio, "dark_ratio")


@dataclass(frozen=True)
class Defect:
    kind: str
    score: float
    bbox_xyxy: tuple[float, float, float, float]
    mask_path: str | None = None
    area_px: float | None = None
    length_px: float | None = None
    orientation_deg: float | None = None
    severity: str | None = None

    def __post_init__(self) -> None:
        unit_interval(self.score, "defect score")
        x1, y1, x2, y2 = self.bbox_xyxy
        if not all(isfinite(v) for v in self.bbox_xyxy) or not (0 <= x1 < x2 and 0 <= y1 < y2):
            raise ValueError("bbox must be finite, nonnegative original-image xyxy")


@dataclass(frozen=True)
class Prediction:
    defect_score: float  # Model score, NOT a calibrated probability by default.
    model_id: str
    defects: tuple[Defect, ...] = ()

    def __post_init__(self) -> None:
        unit_interval(self.defect_score, "defect_score")
        if not self.model_id:
            raise ValueError("model_id is required")


@dataclass(frozen=True)
class Observation:
    action: LightAction
    frame: Frame
    prediction: Prediction | None
    usable: bool
    quality_reason: str
    capture_ms: float
    inference_ms: float


@dataclass(frozen=True)
class Evidence:
    defect_score: float | None
    uncertainty: float
    valid_views: int

    def __post_init__(self) -> None:
        if self.defect_score is not None:
            unit_interval(self.defect_score, "fused defect score")
        unit_interval(self.uncertainty, "uncertainty")
        if self.valid_views < 0:
            raise ValueError("valid_views cannot be negative")


@dataclass
class InspectionResult:
    inspection_id: str
    part_id: str
    started_at: str
    mode: str
    config: dict
    verdict: Verdict = Verdict.REVIEW
    reason: str = "not_started"
    observations: list[Observation] = field(default_factory=list)
    evidence: Evidence = field(default_factory=lambda: Evidence(None, 1.0, 0))
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)
