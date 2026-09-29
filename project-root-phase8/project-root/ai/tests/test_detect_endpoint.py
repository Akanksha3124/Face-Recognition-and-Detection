"""
End-to-end tests for POST /detect through the real FastAPI app (image
upload -> validation -> quality -> detection -> response), not just the
underlying modules in isolation.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.inference.model_registry import DETECTOR_PROTOTXT, DETECTOR_WEIGHTS
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"
client = TestClient(app)

pytestmark = pytest.mark.skipif(
    not (DETECTOR_PROTOTXT.exists() and DETECTOR_WEIGHTS.exists()),
    reason="Face detector weights not downloaded — run `python scripts/download_models.py` from ai/ first",
)


def upload(filename: str, content_type: str = "image/jpeg"):
    with open(FIXTURES / filename, "rb") as f:
        return client.post("/detect", files={"file": (filename, f, content_type)})


def test_detect_returns_face_and_quality_for_good_image():
    response = upload("sample_face.jpg")
    assert response.status_code == 200
    body = response.json()
    assert body["quality"]["passed"] is True
    assert len(body["faces"]) >= 1
    assert body["faces"][0]["confidence"] > 0.9


def test_detect_returns_empty_list_for_image_without_face():
    response = upload("sample_no_face.jpg")
    assert response.status_code == 200
    body = response.json()
    assert body["faces"] == []


def test_detect_reports_quality_failure_for_blurry_image():
    response = upload("sample_blurry.jpg")
    assert response.status_code == 200
    body = response.json()
    assert body["quality"]["is_blurry"] is True
    assert body["quality"]["passed"] is False


def test_detect_rejects_non_image_content_type():
    response = client.post("/detect", files={"file": ("notes.txt", b"hello world", "text/plain")})
    assert response.status_code == 415


def test_detect_rejects_corrupt_image_bytes():
    response = client.post(
        "/detect", files={"file": ("fake.jpg", b"this is not a real jpeg", "image/jpeg")}
    )
    assert response.status_code == 422


def test_detect_rejects_empty_file():
    response = client.post("/detect", files={"file": ("empty.jpg", b"", "image/jpeg")})
    assert response.status_code == 422


def test_detect_rejects_oversized_upload(monkeypatch):
    import app.api.router as router_module

    monkeypatch.setattr(router_module, "MAX_UPLOAD_SIZE_BYTES", 100)  # tiny limit for this test
    with open(FIXTURES / "sample_face.jpg", "rb") as f:
        response = client.post("/detect", files={"file": ("sample_face.jpg", f, "image/jpeg")})
    assert response.status_code == 413


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
