"""Single inspection transaction: light -> fresh capture -> infer -> fuse -> decide."""

import time
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from revision.config import AppConfig
from revision.domain import InspectionResult, Observation, Verdict
from revision.ports import Camera, Fusion, Lighting, LightPolicy, Predictor, ResultStore


class InspectionBusyError(RuntimeError):
    pass


class InspectionEngine:
    def __init__(
        self,
        config: AppConfig,
        camera: Camera,
        lights: Lighting,
        model: Predictor,
        policy: LightPolicy,
        fusion: Fusion,
        store: ResultStore,
    ) -> None:
        self.config, self.camera, self.lights = config, camera, lights
        self.model, self.policy, self.fusion, self.store = model, policy, fusion, store
        self._lock = Lock()

    def inspect(self, part_id: str) -> InspectionResult:
        if not part_id.strip() or len(part_id) > 128:
            raise ValueError("part_id must contain 1..128 characters")
        if not self._lock.acquire(blocking=False):
            raise InspectionBusyError("another inspection is using this station")
        try:
            return self._inspect(part_id)
        finally:
            self._lock.release()

    def _inspect(self, part_id: str) -> InspectionResult:
        cfg = self.config.inspection
        start = time.monotonic()
        result = InspectionResult(
            uuid4().hex,
            part_id,
            datetime.now(UTC).isoformat(),
            self.config.mode,
            self.config.snapshot(),
        )
        directory = self.config.output_dir / "captures" / result.inspection_id

        def expired() -> bool:
            return (time.monotonic() - start) * 1000 >= cfg.budget_ms

        try:
            directory.mkdir(parents=True, exist_ok=False)
            self.lights.off()
            result.reason = "view_budget_exhausted"
            while len(result.observations) < cfg.max_views:
                if expired():
                    result.reason = "time_budget_exhausted"
                    break
                action = self.policy.select(self.config.actions, result.observations)
                if action is None:
                    result.reason = "actions_exhausted"
                    break
                if action not in self.config.actions or any(
                    o.action.id == action.id for o in result.observations
                ):
                    raise ValueError("policy returned an unknown or repeated action")
                self.lights.apply(action)  # Must return only after hardware ACK.
                time.sleep(action.settle_ms / 1000)
                if expired():
                    result.reason = "time_budget_exhausted"
                    break
                before_capture = time.monotonic()
                frame = self.camera.capture(action, directory)
                capture_ms = (time.monotonic() - before_capture) * 1000
                if frame.action_id != action.id or any(
                    o.frame.id == frame.id for o in result.observations
                ):
                    raise ValueError("camera returned a mismatched or duplicate frame")
                reason = "ok"
                if frame.saturation_ratio > cfg.max_saturation_ratio:
                    reason = "overexposed"
                elif frame.dark_ratio > cfg.max_dark_ratio:
                    reason = "underexposed"
                prediction = None
                before_inference = time.monotonic()
                if reason == "ok" and not expired():
                    prediction = self.model.predict(frame)
                    for defect in prediction.defects:
                        if defect.bbox_xyxy[2] > frame.width or defect.bbox_xyxy[3] > frame.height:
                            raise ValueError("model bbox exceeds original frame dimensions")
                inference_ms = (time.monotonic() - before_inference) * 1000
                usable = prediction is not None and reason == "ok"
                result.observations.append(
                    Observation(
                        action,
                        frame,
                        prediction,
                        usable,
                        reason,
                        capture_ms,
                        inference_ms,
                    )
                )
                result.evidence = self.fusion.combine(result.observations)
                if expired():
                    result.reason = "time_budget_exhausted"
                    break
                score = result.evidence.defect_score
                if usable and score is not None:
                    if score >= cfg.fail_threshold:
                        result.verdict, result.reason = Verdict.FAIL, "defect_evidence"
                        break
                    if (
                        score <= cfg.pass_threshold
                        and result.evidence.valid_views >= cfg.min_pass_views
                    ):
                        result.verdict, result.reason = Verdict.PASS, "pass_threshold_met"
                        break
        except Exception as error:
            result.verdict, result.reason = Verdict.ERROR, "inspection_error"
            result.errors.append(f"{type(error).__name__}: {error}")
        finally:
            try:
                self.lights.off()
            except Exception as error:
                result.verdict, result.reason = Verdict.ERROR, "lighting_shutdown_failed"
                result.errors.append(f"{type(error).__name__}: {error}")
            result.duration_ms = (time.monotonic() - start) * 1000
        # A failed durable write raises: callers must not announce a successful inspection.
        self.store.save(result)
        return result
