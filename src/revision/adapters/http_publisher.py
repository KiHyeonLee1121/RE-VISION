"""HTTPS JSON gateway hook. This is NOT an implementation of the WISE-PaaS vendor API."""

import json
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a bearer token to a redirected host.


class HttpPublisher:
    def __init__(self, url: str, token: str, timeout_s: float = 5) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("telemetry endpoint must be HTTPS without credentials in its URL")
        if not token or not 0 < timeout_s <= 30:
            raise ValueError("telemetry token and a 0..30 second timeout are required")
        self.url, self.token, self.timeout_s = url, token, timeout_s
        self.opener = build_opener(_NoRedirect())

    def publish(self, event: dict) -> None:
        request = Request(
            self.url,
            data=json.dumps(event, allow_nan=False).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
                "Idempotency-Key": event["event_id"],
            },
            method="POST",
        )
        with self.opener.open(request, timeout=self.timeout_s) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError("telemetry gateway did not acknowledge the event")
