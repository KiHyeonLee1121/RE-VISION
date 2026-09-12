"""Local result and telemetry outbox are committed in one SQLite transaction."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from revision.domain import InspectionResult
from revision.ports import Publisher


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS inspections (
                    id TEXT PRIMARY KEY, started_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    id TEXT PRIMARY KEY REFERENCES inspections(id),
                    payload TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT, delivered INTEGER NOT NULL DEFAULT 0
                );
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def save(self, result: InspectionResult) -> None:
        payload = json.dumps(result.to_dict(), ensure_ascii=False, allow_nan=False)
        # Exclude local filesystem paths and raw images from cloud telemetry.
        event = {
            "schema_version": 1,
            "event_id": result.inspection_id,
            "part_id": result.part_id,
            "started_at": result.started_at,
            "mode": result.mode,
            "verdict": result.verdict,
            "reason": result.reason,
            "defect_score": result.evidence.defect_score,
            "uncertainty": result.evidence.uncertainty,
            "duration_ms": result.duration_ms,
            "view_count": len(result.observations),
            "reinspection": len(result.observations) > 1,
            "observations": [
                {
                    "action_id": o.action.id,
                    "channel": o.action.channel,
                    "direction_deg": o.action.direction_deg,
                    "intensity": o.action.intensity,
                    "usable": o.usable,
                    "quality_reason": o.quality_reason,
                    "inference_ms": o.inference_ms,
                    "model_id": o.prediction.model_id if o.prediction else None,
                    "defect_score": o.prediction.defect_score if o.prediction else None,
                    "defects": [
                        {
                            "kind": d.kind,
                            "score": d.score,
                            "bbox_xyxy": d.bbox_xyxy,
                            "area_px": d.area_px,
                            "length_px": d.length_px,
                            "orientation_deg": d.orientation_deg,
                            "severity": d.severity,
                        }
                        for d in o.prediction.defects
                    ]
                    if o.prediction
                    else [],
                }
                for o in result.observations
            ],
        }
        with self._connect() as db:
            db.execute(
                "INSERT INTO inspections VALUES (?, ?, ?)",
                (
                    result.inspection_id,
                    result.started_at,
                    payload,
                ),
            )
            db.execute(
                "INSERT INTO outbox (id, payload) VALUES (?, ?)",
                (
                    result.inspection_id,
                    json.dumps(event, ensure_ascii=False, allow_nan=False),
                ),
            )

    def get(self, inspection_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM inspections WHERE id = ?", (inspection_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def recent(self, limit: int = 20) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT payload FROM inspections ORDER BY started_at DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def flush(self, publisher: Publisher, limit: int = 100) -> dict:
        # Single dispatcher recommended. At-least-once delivery; deduplicate by event_id remotely.
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, payload FROM outbox WHERE delivered=0 ORDER BY rowid LIMIT ?",
                (limit,),
            ).fetchall()
        delivered = failed = 0
        for event_id, payload in rows:
            try:
                publisher.publish(json.loads(payload))
            except Exception as error:
                failed += 1
                with self._connect() as db:
                    # Store the exception type only: transport errors may include credentials.
                    db.execute(
                        "UPDATE outbox SET attempts=attempts+1, last_error=? WHERE id=?",
                        (type(error).__name__, event_id),
                    )
            else:
                delivered += 1
                with self._connect() as db:
                    db.execute(
                        "UPDATE outbox SET delivered=1, attempts=attempts+1, "
                        "last_error=NULL WHERE id=?",
                        (event_id,),
                    )
        return {"delivered": delivered, "failed": failed}
