"""Optional local API. Run ONE worker: the camera and LED controller are exclusive devices."""

from contextlib import asynccontextmanager

from revision.config import AppConfig
from revision.inspection import InspectionBusyError
from revision.service import open_station


def create_app(config: AppConfig):
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field

    class InspectRequest(BaseModel):
        part_id: str = Field(min_length=1, max_length=128, pattern=r"\S")

    @asynccontextmanager
    async def lifespan(app):
        with open_station(config) as station:
            app.state.station = station
            yield

    app = FastAPI(title="RE-VISION station", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "ready", "mode": config.mode, "schema_version": 1}

    @app.post("/inspections")
    def inspect(request: InspectRequest):
        try:
            return app.state.station.inspect(request.part_id).to_dict()
        except InspectionBusyError as error:
            raise HTTPException(409, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/inspections")
    def recent(limit: int = 20):
        return app.state.station.store.recent(limit)

    @app.get("/inspections/{inspection_id}")
    def get(inspection_id: str):
        result = app.state.station.store.get(inspection_id)
        if result is None:
            raise HTTPException(404, "inspection not found")
        return result

    return app
