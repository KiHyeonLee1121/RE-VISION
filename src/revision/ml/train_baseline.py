"""Small logistic image classifier to exercise dataset -> training -> ONNX -> runtime.

This is an integration baseline, NOT the proposed scratch/dent detection architecture.
It does not localize defects or claim calibrated confidence. No pretrained downloads.
"""

import argparse
import hashlib
import json
from pathlib import Path

from revision.data.manifest import load_dataset
from revision.ml.preprocessing import prepare_rgb


def train(train_path: Path, val_path: Path, output: Path, epochs: int = 200) -> dict:
    import numpy as np
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    if not 1 <= epochs <= 10000:
        raise ValueError("epochs must be in [1, 10000]")
    training, validation = load_dataset(train_path), load_dataset(val_path)
    for key in ("part_id", "session_id", "sha256"):
        if {r[key] for r in training} & {r[key] for r in validation}:
            raise ValueError(f"train/val leakage through {key}")
    for split in (training, validation):
        if {r["label"] for r in split} != {"clean", "defective"}:
            raise ValueError("train and val must each contain clean and defective parts")
    width = height = 32
    mean, std = (0.5,) * 3, (0.5,) * 3

    def tensors(rows):
        images = [prepare_rgb(Path(r["image_path"]), width, height, mean, std)[0] for r in rows]
        x = np.concatenate(images).reshape(len(rows), -1)
        y = np.asarray([r["label"] == "defective" for r in rows], dtype=np.float32)
        return x, y

    x, y = tensors(training)
    vx, vy = tensors(validation)
    weights = np.zeros(x.shape[1], dtype=np.float32)
    bias = np.float32(0)
    # Scale updates by feature count so the small starter remains numerically stable.
    learning_rate = 0.5 / x.shape[1]

    def sigmoid(values):
        return 1 / (1 + np.exp(-np.clip(values, -40, 40)))

    for _ in range(epochs):
        residual = sigmoid(x @ weights + bias) - y
        weights -= learning_rate * (x.T @ residual / len(y) + 0.01 * weights)
        bias -= 0.1 * residual.mean()
    scores = sigmoid(vx @ weights + bias)
    metrics = {
        "baseline": "32x32 RGB logistic classifier (integration only)",
        "epochs": epochs,
        "train_images": len(training),
        "val_images": len(validation),
        "validation_image_accuracy_at_0_5": float(((scores >= 0.5) == vy).mean()),
        "validation_bce": float(
            -np.mean(vy * np.log(scores + 1e-7) + (1 - vy) * np.log(1 - scores + 1e-7))
        ),
        "confidence_calibrated": False,
        "train_manifest_sha256": hashlib.sha256(train_path.read_bytes()).hexdigest(),
        "val_manifest_sha256": hashlib.sha256(val_path.read_bytes()).hexdigest(),
    }
    graph = helper.make_graph(
        [
            helper.make_node("Flatten", ["images"], ["flat"], axis=1),
            helper.make_node("MatMul", ["flat", "weights"], ["linear"]),
            helper.make_node("Add", ["linear", "bias"], ["logit"]),
            helper.make_node("Sigmoid", ["logit"], ["defect_score"]),
        ],
        "revision-logistic-baseline",
        [helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, height, width])],
        [helper.make_tensor_value_info("defect_score", TensorProto.FLOAT, [1, 1])],
        [
            numpy_helper.from_array(weights.reshape(-1, 1), "weights"),
            numpy_helper.from_array(np.asarray([bias], dtype=np.float32), "bias"),
        ],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.checker.check_model(model)
    output.mkdir(parents=True, exist_ok=False)
    model_path = output / "model.onnx"
    onnx.save_model(model, model_path)
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "model_id": "logistic-" + digest[:12],
        "model_path": "model.onnx",
        "sha256": digest,
        "task": "binary_classification",
        "width": width,
        "height": height,
        "color": "RGB",
        "layout": "NCHW",
        "dtype": "float32",
        "resize": "letterbox",
        "mean": list(mean),
        "std": list(std),
        "pad_value": 114,
        "input_name": "images",
        "output_name": "defect_score",
        "output_kind": "defect_probability",
        "providers": ["CPUExecutionProvider"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--val", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=200)
    args = parser.parse_args()
    print(json.dumps(train(args.train, args.val, args.output, args.epochs), indent=2))


if __name__ == "__main__":
    main()
