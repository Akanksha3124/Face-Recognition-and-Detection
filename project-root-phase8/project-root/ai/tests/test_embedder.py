"""
Unit tests for app/face_embedding/embedder.py, run against the real
ONNX embedding model (see model_registry.py — needs weights downloaded
via scripts/download_models.py, same as test_detector.py needs the
detector weights).
"""
import cv2
import numpy as np
import pytest

from app.face_detection.detector import DetectedFace, detect_faces
from app.face_embedding.embedder import EMBEDDING_DIM, align_face, generate_embedding
from app.inference.model_registry import ModelRegistry

FIXTURES = "tests/fixtures"


def _load(name: str) -> np.ndarray:
    image = cv2.imread(f"{FIXTURES}/{name}")
    assert image is not None, f"fixture {name} failed to load"
    return image


def _detected_face(image: np.ndarray) -> DetectedFace:
    faces = detect_faces(image)
    assert len(faces) == 1
    return faces[0]


def test_align_face_produces_112x112_image():
    image = _load("sample_face.jpg")
    face = _detected_face(image)
    aligned = align_face(image, face)
    assert aligned.shape[:2] == (112, 112)


def test_generate_embedding_returns_512d_unit_vector():
    image = _load("sample_face.jpg")
    face = _detected_face(image)
    aligned = align_face(image, face)
    embedding = generate_embedding(aligned)

    assert len(embedding) == EMBEDDING_DIM
    norm = float(np.linalg.norm(embedding))
    assert norm == pytest.approx(1.0, abs=1e-4)  # L2-normalized, as documented


def test_embedding_is_deterministic():
    image = _load("sample_face.jpg")
    face = _detected_face(image)
    aligned = align_face(image, face)

    embedding_a = generate_embedding(aligned)
    embedding_b = generate_embedding(aligned)
    assert embedding_a == embedding_b


def test_same_face_more_similar_than_different_crops():
    """
    Sanity check that the embedding actually encodes something about
    the face, not noise: the same face compared to itself should have
    a near-perfect cosine similarity, and meaningfully higher than its
    similarity to a patch of the no-face background image.
    """
    face_image = _load("sample_face.jpg")
    face = _detected_face(face_image)
    aligned_face = align_face(face_image, face)
    face_embedding = np.array(generate_embedding(aligned_face))

    self_similarity = float(np.dot(face_embedding, face_embedding))
    assert self_similarity == pytest.approx(1.0, abs=1e-4)

    background_image = _load("sample_no_face.jpg")
    bg_h, bg_w = background_image.shape[:2]
    # No face to detect in this fixture, so just take a same-sized
    # arbitrary crop from it as a "definitely not the same face" comparison.
    fake_region = DetectedFace(x1=0, y1=0, x2=min(200, bg_w), y2=min(200, bg_h))
    aligned_bg = align_face(background_image, fake_region)
    bg_embedding = np.array(generate_embedding(aligned_bg))

    cross_similarity = float(np.dot(face_embedding, bg_embedding))
    assert cross_similarity < self_similarity


def test_model_registry_raises_clear_error_when_embedder_weights_missing(monkeypatch, tmp_path):
    ModelRegistry.reset()
    monkeypatch.setattr(
        "app.inference.model_registry.EMBEDDER_WEIGHTS", tmp_path / "does_not_exist.onnx"
    )
    with pytest.raises(RuntimeError, match="download_models.py"):
        ModelRegistry.get_embedder()
    ModelRegistry.reset()
