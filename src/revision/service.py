"""Composition root: add adapter selection here, keep the inspection loop unchanged."""

from contextlib import ExitStack, contextmanager

from revision.adapters.simulation import (
    DemoCamera,
    DemoPredictor,
    MockLighting,
    ReplayCamera,
    ReplayPredictor,
)
from revision.adapters.sqlite_store import SQLiteStore
from revision.config import AppConfig
from revision.fusion import MaxScoreFusion
from revision.inspection import InspectionEngine
from revision.policies import CoveragePolicy


@contextmanager
def open_station(config: AppConfig):
    with ExitStack() as stack:
        # Load the model before opening physical devices.
        model = None
        if config.mode != "demo" and config.model_manifest is not None:
            from revision.adapters.onnx_model import OnnxBinaryClassifier

            model = OnnxBinaryClassifier(config.model_manifest)
        if config.mode == "live":
            from revision.adapters.opencv_camera import OpenCVCamera
            from revision.adapters.serial_lights import SerialLighting

            camera = OpenCVCamera(config.camera)
            stack.callback(camera.close)
            lights = SerialLighting(config.serial)
        elif config.mode == "replay":
            camera = ReplayCamera(config.replay_manifest)
            stack.callback(camera.close)
            lights = MockLighting()
            model = model or ReplayPredictor(camera)
        else:
            camera = DemoCamera(config.scenario)
            stack.callback(camera.close)
            lights = MockLighting()
            model = DemoPredictor(config.scenario)
        stack.callback(lights.close)
        store = SQLiteStore(config.output_dir / "revision.db")
        yield InspectionEngine(
            config, camera, lights, model, CoveragePolicy(), MaxScoreFusion(), store
        )
