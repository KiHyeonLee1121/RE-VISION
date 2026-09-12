import json
from dataclasses import replace

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torchvision")
pytest.importorskip("onnxruntime")
pytest.importorskip("onnx")

from PIL import Image

from revision.adapters.onnx_model import OnnxBinaryClassifier
from revision.ml.artifacts import latest_checkpoint
from revision.ml.export_torch import export_best
from revision.ml.train_torch import TrainingConfig, build_model, train


@pytest.fixture
def manifests(tmp_path):
    result = []
    for name, offset in [("train", 0), ("val", 5)]:
        rows = []
        for i in range(4):
            path = tmp_path / f"{name}-{i}.png"
            Image.new("RGB", (64, 48), (40 + i * 40 + offset,) * 3).save(path)
            rows.append(
                {
                    "sample_id": path.stem,
                    "part_id": path.stem,
                    "session_id": name,
                    "light_id": "front",
                    "image_path": path.name,
                    "label": "clean" if i < 2 else "defective",
                }
            )
        manifest = tmp_path / f"{name}.jsonl"
        manifest.write_text("\n".join(json.dumps(row) for row in rows))
        result.append(manifest)
    return result


def small_config(epochs):
    return TrainingConfig(
        architecture="tiny_conv",
        pretrained=False,
        width=32,
        height=32,
        epochs=epochs,
        batch_size=2,
        device="cpu",
        amp=False,
        num_workers=0,
    )


def test_epoch_resume_matches_uninterrupted_and_exports(tmp_path, manifests):
    torch.set_num_threads(1)
    run = tmp_path / "drive-run"
    first = train(*manifests, small_config(1), run, tmp_path / "local1", code_revision="test")
    assert first["completed_epoch"] == 1
    saved = latest_checkpoint(run)
    resumed = train(
        *manifests,
        small_config(2),
        run,
        tmp_path / "new-runtime",
        resume=True,
        code_revision="test",
    )
    assert resumed["completed_epoch"] == 2
    assert saved.is_file()
    uninterrupted = tmp_path / "full-run"
    train(*manifests, small_config(2), uninterrupted, tmp_path / "local2", code_revision="test")
    a = torch.load(latest_checkpoint(run), map_location="cpu", weights_only=True)
    b = torch.load(latest_checkpoint(uninterrupted), map_location="cpu", weights_only=True)
    for key in a["model"]:
        torch.testing.assert_close(a["model"][key], b["model"][key], rtol=0, atol=0)
    exported = export_best(run, manifests[1], tmp_path / "export-work")
    assert (exported / "model-bundle.zip").is_file()
    assert OnnxBinaryClassifier(exported / "manifest.json")
    assert json.loads((exported / "metrics.json").read_text())["onnx_verification"]


def test_resume_rejects_changed_settings_code_and_data(tmp_path, manifests):
    run = tmp_path / "drive-run"
    config = small_config(1)
    train(*manifests, config, run, tmp_path / "work", code_revision="original")
    with pytest.raises(FileExistsError):
        train(*manifests, config, run, tmp_path / "work")
    with pytest.raises(ValueError, match="config mismatch"):
        train(*manifests, replace(config, batch_size=4), run, tmp_path / "work", resume=True)
    with pytest.raises(ValueError, match="code revision"):
        train(*manifests, config, run, tmp_path / "work", resume=True, code_revision="changed")
    rows = [json.loads(line) for line in manifests[0].read_text().splitlines()]
    rows[0]["label"] = "defective"
    manifests[0].write_text("\n".join(json.dumps(row) for row in rows))
    with pytest.raises(ValueError, match="dataset/split"):
        train(*manifests, config, run, tmp_path / "work", resume=True, code_revision="original")


def test_mobilenet_contract_without_pretrained_download():
    torch.set_num_threads(1)
    model = build_model(TrainingConfig(pretrained=False)).eval()
    with torch.no_grad():
        assert model(torch.zeros(2, 3, 224, 224)).shape == (2, 1)


def test_mobilenet_training_and_export_without_download(tmp_path, manifests):
    torch.set_num_threads(1)
    config = TrainingConfig(
        pretrained=False,
        width=64,
        height=64,
        epochs=1,
        batch_size=2,
        device="cpu",
        amp=False,
        num_workers=0,
    )
    run = tmp_path / "mobilenet-run"
    train(*manifests, config, run, tmp_path / "local", code_revision="test")
    result = export_best(run, manifests[1], tmp_path / "export")
    manifest = json.loads((result / "manifest.json").read_text())
    assert manifest["model_id"].startswith("mobilenet_v3_small-")
