"""
Integration tests for POST /embed, run against the real FastAPI app
with the real ONNX model (see test_embedder.py's fixture note — needs
weights downloaded via scripts/download_models.py).
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
FIXTURES = "tests/fixtures"


def _upload(name: str, content_type: str = "image/jpeg"):
    with open(f"{FIXTURES}/{name}", "rb") as f:
        return {"file": (name, f.read(), content_type)}


def test_embed_single_face_image_succeeds():
    response = client.post("/embed", files=_upload("sample_face.jpg"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["embedding"]) == 512
    assert body["model_version"]
    assert body["face_used"]["confidence"] > 0.5  # came from auto-detection
    assert "quality" in body


def test_embed_no_face_image_rejected():
    response = client.post("/embed", files=_upload("sample_no_face.jpg"))
    assert response.status_code == 422
    assert "no face" in response.json()["detail"].lower()


def test_embed_multiple_faces_rejected_without_explicit_box():
    response = client.post("/embed", files=_upload("sample_two_faces.jpg"))
    assert response.status_code == 422
    assert "faces detected" in response.json()["detail"].lower()


def test_embed_multiple_faces_succeeds_with_explicit_box():
    """The caller picks a face from a multi-face image by supplying its
    box explicitly — this is the intended way to resolve the ambiguity
    the previous test rejects."""
    with open(f"{FIXTURES}/sample_two_faces.jpg", "rb") as f:
        raw = f.read()
    response = client.post(
        "/embed",
        files={"file": ("sample_two_faces.jpg", raw, "image/jpeg")},
        data={"x1": 205, "y1": 180, "x2": 361, "y2": 386},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["embedding"]) == 512
    # Explicit box -> no detection was run for it -> confidence is None
    assert body["face_used"]["confidence"] is None


def test_embed_explicit_box_out_of_bounds_rejected():
    response = client.post(
        "/embed",
        files=_upload("sample_face.jpg"),
        data={"x1": 0, "y1": 0, "x2": 99999, "y2": 99999},
    )
    assert response.status_code == 422
    assert "out of bounds" in response.json()["detail"].lower()


def test_embed_partial_box_rejected():
    """x1/y1/x2/y2 must be given together, not partially."""
    response = client.post(
        "/embed",
        files=_upload("sample_face.jpg"),
        data={"x1": 10, "y1": 10},
    )
    assert response.status_code == 422
    assert "together" in response.json()["detail"].lower()


def test_embed_tiny_face_box_rejected():
    response = client.post(
        "/embed",
        files=_upload("sample_face.jpg"),
        data={"x1": 10, "y1": 10, "x2": 15, "y2": 15},
    )
    assert response.status_code == 422
    assert "too small" in response.json()["detail"].lower()


def test_embed_rejects_non_image_content_type():
    response = client.post("/embed", files={"file": ("test.txt", b"not an image", "text/plain")})
    assert response.status_code == 415


def test_embed_rejects_corrupt_image_bytes():
    response = client.post("/embed", files={"file": ("bad.jpg", b"not a real jpeg", "image/jpeg")})
    assert response.status_code == 422
