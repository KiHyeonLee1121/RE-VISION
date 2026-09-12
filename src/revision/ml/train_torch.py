"""Resumable GPU binary-classification baseline for Colab and ordinary workstations.

Training infrastructure, not a finalized scratch/dent detector or segmenter.
"""

import copy
import json
import math
import platform
import time
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from revision.data.manifest import load_dataset
from revision.data.staging import dataset_signature
from revision.ml.artifacts import atomic_json, latest_checkpoint, save_checkpoint
from revision.ml.preprocessing import prepare_rgb

MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)


@dataclass(frozen=True)
class TrainingConfig:
    architecture: str = "mobilenet_v3_small"
    pretrained: bool = True
    epochs: int = 20
    batch_size: int = 16
    learning_rate: float = 3e-4
    weight_decay: float = 1e-4
    width: int = 224
    height: int = 224
    seed: int = 42
    num_workers: int = 2
    device: str = "cuda"
    amp: bool = True

    def __post_init__(self) -> None:
        if self.architecture not in {"mobilenet_v3_small", "tiny_conv"}:
            raise ValueError("unsupported training architecture")
        if self.architecture == "tiny_conv" and self.pretrained:
            raise ValueError("tiny_conv has no pretrained weights")
        if self.device not in {"cuda", "cpu"}:
            raise ValueError("device must be cuda or cpu")
        for key in ("epochs", "batch_size", "width", "height", "seed", "num_workers"):
            if type(getattr(self, key)) is not int:
                raise ValueError(f"{key} must be an integer")
        if not 1 <= self.epochs <= 10000 or self.batch_size < 1 or not 0 <= self.num_workers <= 16:
            raise ValueError("invalid epochs, batch_size or num_workers")
        if min(self.width, self.height) < 32:
            raise ValueError("input dimensions must be at least 32")
        if self.architecture == "mobilenet_v3_small" and min(self.width, self.height) < 64:
            raise ValueError("MobileNet inputs must be at least 64 for small training batches")
        if not math.isfinite(self.learning_rate) or self.learning_rate <= 0:
            raise ValueError("learning_rate must be finite and positive")
        if not math.isfinite(self.weight_decay) or self.weight_decay < 0:
            raise ValueError("weight_decay must be finite and nonnegative")

    @classmethod
    def from_toml(cls, path: Path):
        with path.open("rb") as file:
            return cls(**tomllib.load(file))


def build_model(config: TrainingConfig, *, initialize_pretrained: bool = False):
    from torch import nn

    if config.architecture == "tiny_conv":
        return nn.Sequential(
            nn.Conv2d(3, 8, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(8, 1),
        )
    from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

    weights = MobileNet_V3_Small_Weights.DEFAULT if initialize_pretrained else None
    model = mobilenet_v3_small(weights=weights)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, 1)
    return model


class ImageDataset:
    def __init__(self, rows: list[dict], config: TrainingConfig):
        self.rows, self.config = rows, config

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        import torch

        row = self.rows[index]
        tensor, _ = prepare_rgb(
            Path(row["image_path"]),
            self.config.width,
            self.config.height,
            MEAN,
            STD,
        )
        return torch.from_numpy(tensor[0]), torch.tensor(
            [float(row["label"] == "defective")],
            dtype=torch.float32,
        )


def _validated_splits(train_manifest: Path, val_manifest: Path) -> dict[str, list[dict]]:
    splits = {"train": load_dataset(train_manifest), "val": load_dataset(val_manifest)}
    for key in ("part_id", "session_id", "sha256"):
        if {r[key] for r in splits["train"]} & {r[key] for r in splits["val"]}:
            raise ValueError(f"train/val leakage through {key}")
    for name, rows in splits.items():
        if {r["label"] for r in rows} != {"clean", "defective"}:
            raise ValueError(f"{name} requires clean and defective labels")
    return splits


def _epoch(model, loader, device, optimizer=None, scaler=None, amp=False) -> dict:
    import torch

    training = optimizer is not None
    model.train(training)
    total_loss, correct, count = 0.0, 0, 0
    for images, labels in loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        if training:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(training):
            with torch.autocast(device.type, dtype=torch.float16, enabled=amp):
                logits = model(images)
                loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels)
            if not torch.isfinite(loss):
                raise ValueError("non-finite training/validation loss")
            if training:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
        total_loss += float(loss.detach()) * len(labels)
        correct += int(((logits.detach() >= 0) == (labels >= 0.5)).sum())
        count += len(labels)
    return {"loss": total_loss / count, "image_accuracy_at_0_5": correct / count}


def train(
    train_manifest: Path,
    val_manifest: Path,
    config: TrainingConfig,
    run_dir: Path,
    work_dir: Path,
    *,
    resume: bool = False,
    code_revision: str = "unversioned",
) -> dict:
    import torch
    from torch.utils.data import DataLoader

    if config.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable: select a GPU runtime in Colab, or explicitly use cpu")
    device = torch.device(config.device)
    use_amp = config.amp and device.type == "cuda"
    splits = _validated_splits(train_manifest, val_manifest)
    signature = dataset_signature(splits)
    config_dict = asdict(config)
    checkpoint = None
    if resume:
        checkpoint = torch.load(latest_checkpoint(run_dir), map_location="cpu", weights_only=True)
        original = checkpoint["config"]
        # Extending total epochs is allowed; training semantics and data must be unchanged.
        for key, value in config_dict.items():
            if key != "epochs" and original.get(key) != value:
                raise ValueError(
                    f"resume config mismatch: {key}; start a new run for changed settings"
                )
        if checkpoint["dataset_signature"] != signature:
            raise ValueError("resume dataset/split mismatch")
        if checkpoint["code_revision"] != code_revision:
            raise ValueError("resume code revision mismatch; use the recorded Git commit")
        if config.epochs < checkpoint["epoch"]:
            raise ValueError("total epochs cannot precede the saved epoch")
    elif run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError("run directory is not empty: choose a new run ID or resume=True")
    if run_dir.resolve() == work_dir.resolve():
        raise ValueError("work_dir must differ from the persistent run directory")
    torch.manual_seed(config.seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(config.seed)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
    model = build_model(config, initialize_pretrained=config.pretrained and not resume).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    history, start_epoch, best_loss, best_epoch, best_model = [], 1, math.inf, 0, None
    if checkpoint:
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        scaler.load_state_dict(checkpoint["scaler"])
        history = checkpoint["history"]
        start_epoch = checkpoint["epoch"] + 1
        best_loss, best_epoch, best_model = (
            checkpoint["best_loss"],
            checkpoint["best_epoch"],
            checkpoint["best_model"],
        )
        torch.set_rng_state(checkpoint["torch_rng"])
        if device.type == "cuda":
            torch.cuda.set_rng_state_all(checkpoint["cuda_rng"])
    else:
        import torchvision

        atomic_json(
            run_dir / "run.json",
            {
                "schema_version": 1,
                "config": config_dict,
                "dataset_signature": signature,
                "code_revision": code_revision,
                "python": platform.python_version(),
                "torch": str(torch.__version__),
                "torchvision": str(torchvision.__version__),
                "cuda_runtime": torch.version.cuda,
                "device": torch.cuda.get_device_name() if device.type == "cuda" else "cpu",
                "confidence_calibrated": False,
            },
        )
        # Portable membership/provenance: no temporary /content image paths.
        atomic_json(
            run_dir / "dataset-snapshot.json",
            {
                name: [{k: v for k, v in row.items() if k != "image_path"} for row in rows]
                for name, rows in splits.items()
            },
        )
    validation = DataLoader(
        ImageDataset(splits["val"], config),
        batch_size=config.batch_size,
        num_workers=config.num_workers,
        pin_memory=device.type == "cuda",
        generator=torch.Generator().manual_seed(config.seed),
    )
    for epoch in range(start_epoch, config.epochs + 1):
        started = time.monotonic()
        training = DataLoader(
            ImageDataset(splits["train"], config),
            batch_size=config.batch_size,
            shuffle=True,
            num_workers=config.num_workers,
            pin_memory=device.type == "cuda",
            generator=torch.Generator().manual_seed(config.seed + epoch),
        )
        train_metrics = _epoch(model, training, device, optimizer, scaler, use_amp)
        val_metrics = _epoch(model, validation, device)
        if val_metrics["loss"] < best_loss:
            best_loss, best_epoch = val_metrics["loss"], epoch
            best_model = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        history.append(
            {
                "epoch": epoch,
                "train": train_metrics,
                "val": val_metrics,
                "seconds": time.monotonic() - started,
            }
        )
        payload = {
            "schema_version": 1,
            "epoch": epoch,
            "config": config_dict,
            "code_revision": code_revision,
            "dataset_signature": signature,
            "model": copy.deepcopy(model.state_dict()),
            "optimizer": optimizer.state_dict(),
            "scaler": scaler.state_dict(),
            "torch_rng": torch.get_rng_state(),
            "cuda_rng": torch.cuda.get_rng_state_all() if device.type == "cuda" else [],
            "best_loss": best_loss,
            "best_epoch": best_epoch,
            "best_model": best_model,
            "history": history,
        }
        save_checkpoint(payload, work_dir / "checkpoints", run_dir)
        atomic_json(run_dir / "history.json", history)
        print(json.dumps(history[-1]), flush=True)
    return {
        "completed_epoch": start_epoch - 1 if not history else history[-1]["epoch"],
        "best_epoch": best_epoch,
        "best_validation_loss": best_loss,
        "run_dir": str(run_dir),
    }
