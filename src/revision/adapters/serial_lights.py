"""Versioned JSON-lines contract with an MCU. See hardware/protocol.md."""

import json
from uuid import uuid4

from revision.config import SerialSettings
from revision.domain import LightAction


class SerialLighting:
    def __init__(self, settings: SerialSettings) -> None:
        import serial

        self.serial = serial.Serial(
            settings.port,
            settings.baudrate,
            timeout=settings.timeout_s,
            write_timeout=settings.timeout_s,
        )

    def _command(self, command: str, **payload: object) -> None:
        request_id = uuid4().hex
        message = {"v": 1, "id": request_id, "command": command, **payload}
        self.serial.reset_input_buffer()
        self.serial.write((json.dumps(message) + "\n").encode("utf-8"))
        reply = self.serial.read_until(b"\n", size=2048)
        if not reply.endswith(b"\n"):
            raise TimeoutError("lighting ACK timeout or oversized reply")
        ack = json.loads(reply)
        if ack.get("v") != 1 or ack.get("id") != request_id or ack.get("ok") is not True:
            raise RuntimeError("lighting ACK rejected or mismatched")

    def apply(self, action: LightAction) -> None:
        self._command("set", channel=action.channel, intensity=action.intensity)

    def off(self) -> None:
        self._command("off")

    def close(self) -> None:
        try:
            self.off()
        finally:
            self.serial.close()
