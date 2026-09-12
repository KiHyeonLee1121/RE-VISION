import json

import pytest

from revision.config import AppConfig, InspectionSettings, load_config
from revision.service import open_station


def test_outbox_retries_without_losing_results(tmp_path):
    with open_station(AppConfig(output_dir=tmp_path)) as station:
        result = station.inspect("part")

        class Offline:
            def publish(self, event):
                raise OSError("network unavailable")

        assert station.store.flush(Offline()) == {"delivered": 0, "failed": 1}
        events = []

        class Online:
            def publish(self, event):
                events.append(event)

        assert station.store.flush(Online()) == {"delivered": 1, "failed": 0}
        assert station.store.flush(Online()) == {"delivered": 0, "failed": 0}
        assert events[0]["event_id"] == result.inspection_id
        assert str(tmp_path) not in json.dumps(events[0])
        assert station.store.get(result.inspection_id) is not None


def test_config_resolves_relative_paths_and_rejects_typos(tmp_path):
    path = tmp_path / "demo.toml"
    path.write_text('mode="demo"\noutput_dir="results"\n')
    assert load_config(path).output_dir == tmp_path / "results"
    path.write_text('mode="demo"\n[inspection]\nmax_viewz=5\n')
    with pytest.raises(TypeError):
        load_config(path)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pass_threshold": 0.9, "fail_threshold": 0.1},
        {"budget_ms": float("nan")},
        {"max_views": 0},
        {"max_views": 2, "min_pass_views": 3},
    ],
)
def test_bad_settings_rejected(kwargs):
    with pytest.raises(ValueError):
        InspectionSettings(**kwargs)


def test_live_never_falls_back_to_mock_model():
    with pytest.raises(ValueError, match="live mode requires"):
        AppConfig(mode="live")
