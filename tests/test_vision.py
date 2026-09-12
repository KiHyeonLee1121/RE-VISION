import hashlib
import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("PIL")
pytest.importorskip("onnx")
pytest.importorskip("onnxruntime")

from PIL import Image

from revision.adapters.onnx_model import OnnxBinaryClassifier
from revision.domain import Frame
from revision.ml.preprocessing import prepare_rgb
from revision.ml.train_baseline import train


def test_letterbox_and_coordinate_roundtrip(tmp_path):
    path = tmp_path / "wide.png"
    Image.new("RGB", (200, 100), (255, 0, 0)).save(path)
    tensor, transform = prepare_rgb(path, 100, 100, (0, 0, 0), (1, 1, 1))
    assert tensor.shape == (1, 3, 100, 100)
    assert tensor.dtype == np.float32
    assert tuple(tensor[0, :, 50, 50]) == (1, 0, 0)
    assert transform.to_original((0, 25, 100, 75)) == (0, 0, 200, 100)


def test_actual_training_export_and_onnx_inference(tmp_path):
    manifests = []
    for split, offset in [("train", 0), ("val", 10)]:
        rows = []
        for i, label in enumerate(["clean", "defective"]):
            image = tmp_path / f"{split}-{i}.png"
            shade = 50 + offset if i == 0 else 200 + offset
            Image.new("RGB", (64, 32), (shade,) * 3).save(image)
            rows.append(
                {
                    "sample_id": image.stem,
                    "part_id": image.stem,
                    "session_id": split,
                    "light_id": "front",
                    "image_path": image.name,
                    "label": label,
                }
            )
        manifest = tmp_path / f"{split}.jsonl"
        manifest.write_text("\n".join(json.dumps(r) for r in rows))
        manifests.append(manifest)
    output = tmp_path / "model"
    metrics = train(*manifests, output, epochs=40)
    assert metrics["validation_image_accuracy_at_0_5"] == 1
    model = OnnxBinaryClassifier(output / "manifest.json")
    score = model.predict(
        Frame("a", "front", str(tmp_path / "val-1.png"), 64, 32, "test")
    ).defect_score
    assert 0.5 < score <= 1
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["sha256"] == hashlib.sha256((output / "model.onnx").read_bytes()).hexdigest()
    (output / "model.onnx").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA256"):
        OnnxBinaryClassifier(output / "manifest.json")
