import json
import sys
from types import SimpleNamespace

import pytest

from revision.adapters.serial_lights import SerialLighting
from revision.config import SerialSettings
from revision.domain import LightAction


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.message = None
        self.closed = False
        self.wrong_id = False

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.message = json.loads(data)

    def read_until(self, *args, **kwargs):
        return (
            json.dumps({"v": 1, "id": "wrong" if self.wrong_id else self.message["id"], "ok": True})
            + "\n"
        ).encode()

    def close(self):
        self.closed = True


def test_ack_identity_and_shutdown(monkeypatch):
    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=FakeSerial))
    lights = SerialLighting(SerialSettings(port="test"))
    lights.apply(LightAction("front", 0, 0, 0.5))
    assert lights.serial.message["command"] == "set"
    assert lights.serial.message["channel"] == 0
    lights.serial.wrong_id = True
    with pytest.raises(RuntimeError, match="ACK"):
        lights.off()
    with pytest.raises(RuntimeError):
        lights.close()
    assert lights.serial.closed
