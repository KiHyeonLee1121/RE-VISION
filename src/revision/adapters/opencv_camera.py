"""USB camera prototype. Industrial trigger/timestamp validation needs a vendor adapter."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from revision.config import CameraSettings
from revision.domain import Frame, LightAction


class OpenCVCamera:
    def __init__(self, settings: CameraSettings) -> None:
        import cv2

        self.cv2, self.settings = cv2, settings
        self.device = cv2.VideoCapture(settings.device)
        if not self.device.isOpened():
            self.device.release()
            raise RuntimeError("unable to open the configured camera")
        self.device.set(cv2.CAP_PROP_FRAME_WIDTH, settings.width)
        self.device.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.height)
        self.device.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def capture(self, action: LightAction, output_dir: Path) -> Frame:
        for _ in range(self.settings.flush_frames):
            if not self.device.grab():
                raise RuntimeError("camera buffer flush failed")
        ok, pixels = self.device.read()
        if not ok or pixels is None or pixels.size == 0:
            raise RuntimeError("camera capture failed")
        captured_at = datetime.now(UTC).isoformat()
        gray = self.cv2.cvtColor(pixels, self.cv2.COLOR_BGR2GRAY)
        frame_id = uuid4().hex
        path = output_dir / f"{frame_id}.png"
        if not self.cv2.imwrite(str(path), pixels):
            raise OSError("could not save captured image")
        height, width = gray.shape
        return Frame(
            frame_id,
            action.id,
            str(path),
            width,
            height,
            captured_at,
            float((gray >= 250).mean()),
            float((gray <= 5).mean()),
        )

    def close(self) -> None:
        self.device.release()
