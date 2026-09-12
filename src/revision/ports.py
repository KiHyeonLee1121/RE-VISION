"""Implement these protocols to add hardware, a detector, fusion, or a learned policy."""

from pathlib import Path
from typing import Protocol

from revision.domain import (
    Evidence,
    Frame,
    InspectionResult,
    LightAction,
    Observation,
    Prediction,
)


class Camera(Protocol):
    def capture(self, action: LightAction, output_dir: Path) -> Frame: ...
    def close(self) -> None: ...


class Lighting(Protocol):
    def apply(self, action: LightAction) -> None: ...
    def off(self) -> None: ...
    def close(self) -> None: ...


class Predictor(Protocol):
    def predict(self, frame: Frame) -> Prediction: ...


class Fusion(Protocol):
    def combine(self, observations: list[Observation]) -> Evidence: ...


class LightPolicy(Protocol):
    def select(
        self, actions: tuple[LightAction, ...], observations: list[Observation]
    ) -> LightAction | None: ...


class ResultStore(Protocol):
    def save(self, result: InspectionResult) -> None: ...


class Publisher(Protocol):
    def publish(self, event: dict) -> None:
        """Return only after the receiver acknowledges durable acceptance; raise otherwise."""
        ...
