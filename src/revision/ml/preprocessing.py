"""One aspect-preserving RGB preprocessing contract for export and inference."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LetterboxTransform:
    original_width: int
    original_height: int
    resized_width: int
    resized_height: int
    left: int
    top: int

    def to_original(self, bbox: tuple[float, float, float, float]) -> tuple[float, ...]:
        x1, y1, x2, y2 = bbox
        sx = self.resized_width / self.original_width
        sy = self.resized_height / self.original_height
        return (
            max(0.0, min(self.original_width, (x1 - self.left) / sx)),
            max(0.0, min(self.original_height, (y1 - self.top) / sy)),
            max(0.0, min(self.original_width, (x2 - self.left) / sx)),
            max(0.0, min(self.original_height, (y2 - self.top) / sy)),
        )


def prepare_rgb(
    path: Path,
    width: int,
    height: int,
    mean: tuple[float, ...],
    std: tuple[float, ...],
    pad_value: int = 114,
):
    import numpy as np
    from PIL import Image, ImageOps

    if width < 1 or height < 1 or len(mean) != 3 or len(std) != 3:
        raise ValueError("invalid preprocessing dimensions or RGB normalization")
    if not np.isfinite(mean).all() or not np.isfinite(std).all() or min(std) <= 0:
        raise ValueError("normalization must be finite with positive std")
    with Image.open(path) as source:
        original = ImageOps.exif_transpose(source).convert("RGB")
        ow, oh = original.size
        scale = min(width / ow, height / oh)
        rw, rh = max(1, round(ow * scale)), max(1, round(oh * scale))
        left, top = (width - rw) // 2, (height - rh) // 2
        canvas = Image.new("RGB", (width, height), (pad_value,) * 3)
        canvas.paste(original.resize((rw, rh), Image.Resampling.BILINEAR), (left, top))
        pixels = np.asarray(canvas, dtype=np.float32) / 255.0
    pixels = (pixels - np.asarray(mean, dtype=np.float32)) / np.asarray(std, dtype=np.float32)
    tensor = np.ascontiguousarray(pixels.transpose(2, 0, 1)[None], dtype=np.float32)
    return tensor, LetterboxTransform(ow, oh, rw, rh, left, top)
