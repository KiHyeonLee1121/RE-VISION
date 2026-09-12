"""Deliberately narrow ONNX binary classifier adapter; detectors get separate adapters."""

import hashlib
import json
import math
from pathlib import Path

from revision.domain import Frame, Prediction
from revision.ml.preprocessing import prepare_rgb


class OnnxBinaryClassifier:
    def __init__(self, manifest_path: Path) -> None:
        import onnxruntime as ort

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        required = {
            "schema_version",
            "model_id",
            "model_path",
            "sha256",
            "task",
            "width",
            "height",
            "color",
            "layout",
            "dtype",
            "resize",
            "mean",
            "std",
            "pad_value",
            "input_name",
            "output_name",
            "output_kind",
            "providers",
        }
        if set(manifest) != required:
            raise ValueError(f"manifest keys mismatch: {set(manifest) ^ required}")
        expected = {
            "schema_version": 1,
            "task": "binary_classification",
            "color": "RGB",
            "layout": "NCHW",
            "dtype": "float32",
            "resize": "letterbox",
        }
        if any(manifest[key] != value for key, value in expected.items()):
            raise ValueError("unsupported model contract; implement a separate Predictor adapter")
        if manifest["output_kind"] not in {"defect_probability", "defect_logit"}:
            raise ValueError("output must be one scalar defect probability or logit per image")
        if not manifest["providers"] or any(
            p not in ort.get_available_providers() for p in manifest["providers"]
        ):
            raise ValueError("a requested ONNX provider is unavailable")
        model_path = (manifest_path.parent / manifest["model_path"]).resolve()
        if hashlib.sha256(model_path.read_bytes()).hexdigest() != manifest["sha256"]:
            raise ValueError("model SHA256 mismatch")
        self.manifest = manifest
        self.session = ort.InferenceSession(str(model_path), providers=manifest["providers"])
        inputs, outputs = self.session.get_inputs(), self.session.get_outputs()
        if len(inputs) != 1 or inputs[0].name != manifest["input_name"]:
            raise ValueError("model input name/count mismatch")
        if inputs[0].type != "tensor(float)" or len(inputs[0].shape) != 4:
            raise ValueError("model input must be NCHW float32")
        for actual, configured in zip(
            inputs[0].shape,
            [1, 3, manifest["height"], manifest["width"]],
            strict=True,
        ):
            if isinstance(actual, int) and actual != configured:
                raise ValueError("model input dimensions disagree with manifest")
        if manifest["output_name"] not in {o.name for o in outputs}:
            raise ValueError("model output name mismatch")

    def predict(self, frame: Frame) -> Prediction:
        import numpy as np

        m = self.manifest
        tensor, transform = prepare_rgb(
            Path(frame.path),
            m["width"],
            m["height"],
            tuple(m["mean"]),
            tuple(m["std"]),
            m["pad_value"],
        )
        if (frame.width, frame.height) != (transform.original_width, transform.original_height):
            raise ValueError("frame dimensions disagree with decoded image")
        output = np.asarray(self.session.run([m["output_name"]], {m["input_name"]: tensor})[0])
        if output.size != 1:
            raise ValueError("binary classifier output must contain exactly one score")
        score = float(output.item())
        if not math.isfinite(score):
            raise ValueError("model returned a non-finite score")
        if m["output_kind"] == "defect_logit":
            score = (
                1 / (1 + math.exp(-score))
                if score >= 0
                else math.exp(score) / (1 + math.exp(score))
            )
        return Prediction(score, m["model_id"])
