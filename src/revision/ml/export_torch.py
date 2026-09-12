"""Export the best validation checkpoint, compare native/ONNX outputs, save a Drive bundle."""

import json
import shutil
from pathlib import Path
from uuid import uuid4

from revision.data.manifest import load_dataset
from revision.domain import Frame
from revision.ml.artifacts import atomic_json, latest_checkpoint, sha256_file, verified_copy
from revision.ml.preprocessing import prepare_rgb
from revision.ml.train_torch import MEAN, STD, TrainingConfig, build_model


def export_best(run_dir: Path, val_manifest: Path, work_dir: Path) -> Path:
    import numpy as np
    import onnx
    import torch

    from revision.adapters.onnx_model import OnnxBinaryClassifier

    checkpoint = torch.load(latest_checkpoint(run_dir), map_location="cpu", weights_only=True)
    config = TrainingConfig(**checkpoint["config"])
    validation = load_dataset(val_manifest)
    snapshot = json.loads((run_dir / "dataset-snapshot.json").read_text())["val"]

    def canonical(rows):
        return sorted(
            [{k: v for k, v in row.items() if k != "image_path"} for row in rows],
            key=lambda row: row["sample_id"],
        )

    if canonical(validation) != canonical(snapshot):
        raise ValueError("export validation dataset differs from the training run")
    model = build_model(config).cpu().eval()
    model.load_state_dict(checkpoint["best_model"])
    export_dir = work_dir / ("export-" + uuid4().hex[:8])
    export_dir.mkdir(parents=True, exist_ok=False)
    model_path = export_dir / "model.onnx"
    dummy = torch.zeros(1, 3, config.height, config.width)
    torch.onnx.export(
        model,
        dummy,
        str(model_path),
        input_names=["images"],
        output_names=["defect_logit"],
        opset_version=17,
        dynamo=False,
    )
    onnx.checker.check_model(onnx.load(model_path))
    digest = sha256_file(model_path)
    manifest = {
        "schema_version": 1,
        "model_id": config.architecture + "-" + digest[:12],
        "model_path": "model.onnx",
        "sha256": digest,
        "task": "binary_classification",
        "width": config.width,
        "height": config.height,
        "color": "RGB",
        "layout": "NCHW",
        "dtype": "float32",
        "resize": "letterbox",
        "mean": list(MEAN),
        "std": list(STD),
        "pad_value": 114,
        "input_name": "images",
        "output_name": "defect_logit",
        "output_kind": "defect_logit",
        "providers": ["CPUExecutionProvider"],
    }
    atomic_json(export_dir / "manifest.json", manifest)
    predictor = OnnxBinaryClassifier(export_dir / "manifest.json")
    comparisons = []
    for row in validation[: min(5, len(validation))]:
        tensor, transform = prepare_rgb(
            Path(row["image_path"]),
            config.width,
            config.height,
            MEAN,
            STD,
        )
        with torch.no_grad():
            native = float(torch.sigmoid(model(torch.from_numpy(tensor))).item())
        runtime = predictor.predict(
            Frame(
                row["sample_id"],
                row["light_id"],
                row["image_path"],
                transform.original_width,
                transform.original_height,
                "export-verification",
            )
        ).defect_score
        np.testing.assert_allclose(runtime, native, rtol=1e-3, atol=1e-4)
        comparisons.append({"sample_id": row["sample_id"], "torch": native, "onnx": runtime})
    atomic_json(
        export_dir / "metrics.json",
        {
            "best_epoch": checkpoint["best_epoch"],
            "best_validation_loss": checkpoint["best_loss"],
            "dataset_signature": checkpoint["dataset_signature"],
            "code_revision": checkpoint["code_revision"],
            "history": checkpoint["history"],
            "confidence_calibrated": False,
            "onnx_verification": comparisons,
        },
    )
    target = run_dir / "exports" / digest[:12]
    checksums = {}
    for source in sorted(export_dir.iterdir()):
        checksums[source.name] = verified_copy(source, target / source.name)
    atomic_json(target / "checksums.json", checksums)
    # Zip locally, then copy once to Drive. Target name is model-content-specific.
    archive = Path(shutil.make_archive(str(export_dir), "zip", export_dir))
    verified_copy(archive, target / "model-bundle.zip")
    atomic_json(
        run_dir / "latest-export.json",
        {
            "path": str(target.relative_to(run_dir)),
            "model_sha256": digest,
        },
    )
    return target
