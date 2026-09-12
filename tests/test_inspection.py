import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event

import pytest

from revision.config import AppConfig, InspectionSettings
from revision.domain import Prediction, Verdict
from revision.inspection import InspectionBusyError
from revision.service import open_station


@pytest.mark.parametrize(
    "scenario,verdict,views",
    [
        ("clean", Verdict.PASS, 1),
        ("scratch", Verdict.FAIL, 2),
        ("uncertain", Verdict.REVIEW, 4),
        ("glare", Verdict.PASS, 2),
    ],
)
def test_scenarios_are_persisted_and_lights_off(tmp_path, scenario, verdict, views):
    with open_station(AppConfig(output_dir=tmp_path, scenario=scenario)) as station:
        result = station.inspect("part-001")
        assert result.verdict == verdict
        assert len(result.observations) == views
        assert station.lights.active is None
        assert station.store.get(result.inspection_id)["verdict"] == verdict
        if scenario == "glare":
            assert not result.observations[0].usable
            assert result.observations[0].prediction is None
            assert result.observations[1].action.id == "right_dim"


def test_minimum_pass_views_and_no_repeated_actions(tmp_path):
    config = AppConfig(
        output_dir=tmp_path, scenario="clean", inspection=InspectionSettings(min_pass_views=3)
    )
    with open_station(config) as station:
        result = station.inspect("clean")
        assert result.verdict == Verdict.PASS
        assert result.evidence.valid_views == 3
        assert len({o.action.id for o in result.observations}) == 3


def test_bad_frames_never_become_pass(tmp_path):
    with open_station(AppConfig(output_dir=tmp_path, scenario="clean")) as station:
        original = station.camera.capture
        station.camera.capture = lambda a, p: replace(original(a, p), saturation_ratio=1)
        result = station.inspect("unknown")
        assert result.verdict == Verdict.REVIEW
        assert result.evidence.defect_score is None


@pytest.mark.parametrize("bad_score", [float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_model_output_is_error(tmp_path, bad_score):
    with open_station(AppConfig(output_dir=tmp_path)) as station:
        station.model.predict = lambda _: Prediction(bad_score, "bad-model")
        result = station.inspect("part")
        assert result.verdict == Verdict.ERROR
        assert station.lights.active is None


def test_camera_failure_stored_as_error(tmp_path):
    with open_station(AppConfig(output_dir=tmp_path)) as station:

        def fail(*args):
            raise OSError("camera unplugged")

        station.camera.capture = fail
        result = station.inspect("part")
        assert result.verdict == Verdict.ERROR
        assert station.lights.active is None
        assert station.store.get(result.inspection_id)["reason"] == "inspection_error"


def test_shutdown_failure_overrides_pass(tmp_path):
    with open_station(AppConfig(output_dir=tmp_path, scenario="clean")) as station:
        calls = 0
        original = station.lights.off

        def fail_second_off():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("no ACK")
            original()

        station.lights.off = fail_second_off
        result = station.inspect("part")
        assert result.verdict == Verdict.ERROR
        assert result.reason == "lighting_shutdown_failed"


def test_late_prediction_cannot_pass(tmp_path):
    cfg = AppConfig(output_dir=tmp_path, inspection=InspectionSettings(budget_ms=50))
    with open_station(cfg) as station:

        def late(_):
            time.sleep(0.06)
            return Prediction(0.01, "late-model")

        station.model.predict = late
        result = station.inspect("late")
        assert result.verdict == Verdict.REVIEW
        assert result.reason == "time_budget_exhausted"
        assert station.lights.active is None


def test_duplicate_or_mismatched_frame_is_error(tmp_path):
    with open_station(AppConfig(output_dir=tmp_path)) as station:
        capture = station.camera.capture
        station.camera.capture = lambda a, p: replace(capture(a, p), action_id="wrong-light")
        assert station.inspect("part").verdict == Verdict.ERROR


def test_store_failure_raises_and_releases_lock(tmp_path):
    with open_station(AppConfig(output_dir=tmp_path, scenario="clean")) as station:
        save = station.store.save

        def fail(_):
            raise OSError("disk full")

        station.store.save = fail
        with pytest.raises(OSError, match="disk full"):
            station.inspect("part")
        assert station.lights.active is None
        station.store.save = save
        assert station.inspect("next-part").verdict == Verdict.PASS


def test_only_one_inspection_can_use_hardware(tmp_path):
    entered, release = Event(), Event()
    with open_station(AppConfig(output_dir=tmp_path)) as station:

        def blocked(_):
            entered.set()
            assert release.wait(2)
            return Prediction(0.99, "blocked-model")

        station.model.predict = blocked
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(station.inspect, "first")
            try:
                assert entered.wait(2)
                with pytest.raises(InspectionBusyError):
                    station.inspect("second")
            finally:
                release.set()
            assert future.result().verdict == Verdict.FAIL
