import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from revision.api import create_app
from revision.config import AppConfig


def test_api_inspection_and_history(tmp_path):
    with TestClient(create_app(AppConfig(output_dir=tmp_path))) as client:
        assert client.get("/health").json()["mode"] == "demo"
        response = client.post("/inspections", json={"part_id": "part-001"})
        assert response.status_code == 200
        result = response.json()
        assert result["verdict"] == "FAIL"
        assert client.get(f"/inspections/{result['inspection_id']}").json() == result
        assert len(client.get("/inspections").json()) == 1
        assert client.get("/inspections/missing").status_code == 404
        assert client.post("/inspections", json={"part_id": " "}).status_code == 422
