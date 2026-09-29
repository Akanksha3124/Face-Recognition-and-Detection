"""
Face detection tests, run against the real OpenCV DNN model (weights
downloaded via scripts/download_models.py — see conftest.py for the
session-scoped check that skips these tests with a clear message if
they're missing, rather than failing confusingly deep in cv2 internals).
"""
from pathlib import Path

import cv2
import pytest

from app.face_detection.detector import crop_face, detect_faces
from app.inference.model_registry import DETECTOR_PROTOTXT, DETECTOR_WEIGHTS, ModelRegistry

FIXTURES = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.skipif(
    not (DETECTOR_PROTOTXT.exists() and DETECTOR_WEIGHTS.exists()),
    reason="Face detector weights not downloaded — run `python scripts/download_models.py` from ai/ first",
)


def load(name: str):
    image = cv2.imread(str(FIXTURES / name))
    assert image is not None, f"fixture {name} failed to load"
    return image


def test_detects_face_in_photo_with_a_face():
    faces = detect_faces(load("sample_face.jpg"))
    assert len(faces) >= 1
    assert faces[0].confidence > 0.9  # this fixture detects at ~0.998 in practice


def test_detected_bbox_is_within_image_bounds():
    image = load("sample_face.jpg")
    height, width = image.shape[:2]
    faces = detect_faces(image)
    assert len(faces) >= 1
    face = faces[0]
    assert 0 <= face.x1 < face.x2 <= width
    assert 0 <= face.y1 < face.y2 <= height


def test_no_faces_in_image_without_a_face():
    faces = detect_faces(load("sample_no_face.jpg"))
    assert faces == []


def test_no_face_is_not_an_error_just_an_empty_list():
    # Explicit per the architecture doc: absence of a face is a valid
    # pipeline outcome, not an exception.
    faces = detect_faces(load("sample_no_face.jpg"))
    assert isinstance(faces, list)


def test_faces_sorted_by_confidence_descending():
    faces = detect_faces(load("sample_face.jpg"))
    confidences = [f.confidence for f in faces]
    assert confidences == sorted(confidences, reverse=True)


def test_min_confidence_filters_out_weak_detections():
    # An impossibly high threshold should filter out even a clear face —
    # confirms the "reject extremely poor detections" cutoff is applied,
    # not just decorative.
    faces = detect_faces(load("sample_face.jpg"), min_confidence=0.999999)
    assert faces == []


def test_crop_face_returns_nonempty_region_with_margin():
    image = load("sample_face.jpg")
    faces = detect_faces(image)
    assert len(faces) >= 1
    face = faces[0]

    tight_crop = image[face.y1 : face.y2, face.x1 : face.x2]
    padded_crop = crop_face(image, face, margin_ratio=0.2)

    assert padded_crop.size > 0
    # The margin should make the padded crop at least as large as the
    # tight bounding-box crop in both dimensions.
    assert padded_crop.shape[0] >= tight_crop.shape[0]
    assert padded_crop.shape[1] >= tight_crop.shape[1]


def test_crop_face_stays_within_image_bounds_near_edges():
    """A face box touching the image edge should still produce a valid
    crop — the margin must be clipped, not run off the array."""
    from app.face_detection.detector import DetectedFace

    image = load("sample_face.jpg")
    height, width = image.shape[:2]
    edge_face = DetectedFace(x1=0, y1=0, x2=min(50, width), y2=min(50, height), confidence=0.99)

    crop = crop_face(image, edge_face, margin_ratio=0.5)
    assert crop.size > 0
    assert crop.shape[0] <= height
    assert crop.shape[1] <= width


def test_model_registry_raises_clear_error_when_weights_missing(monkeypatch):
    monkeypatch.setattr("app.inference.model_registry.DETECTOR_PROTOTXT", Path("/nonexistent/deploy.prototxt"))
    monkeypatch.setattr(
        "app.inference.model_registry.DETECTOR_WEIGHTS", Path("/nonexistent/weights.caffemodel")
    )
    ModelRegistry.reset()
    with pytest.raises(RuntimeError, match="download_models.py"):
        ModelRegistry.get_detector()
    ModelRegistry.reset()  # don't leak the broken state into other tests
