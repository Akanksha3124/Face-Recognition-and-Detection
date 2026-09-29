"""
Model loading and singleton cache. Ensures each model is loaded exactly
once at process startup and reused across requests — never per-request
(loading a Caffe/ONNX net from disk on every call would be slow and
wasteful).

Weights are not committed to the repo — run `python scripts/download_models.py`
from ai/ first (see that script for where they come from).
"""
from pathlib import Path

import cv2

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
DETECTOR_PROTOTXT = MODELS_DIR / "face_detection" / "deploy.prototxt"
DETECTOR_WEIGHTS = MODELS_DIR / "face_detection" / "res10_300x300_ssd_iter_140000.caffemodel"


class ModelRegistry:
    _detector = None

    @classmethod
    def get_detector(cls):
        if cls._detector is None:
            if not DETECTOR_PROTOTXT.exists() or not DETECTOR_WEIGHTS.exists():
                raise RuntimeError(
                    "Face detector weights not found. From the ai/ directory, run: "
                    "python scripts/download_models.py "
                    f"(expected files under {MODELS_DIR})"
                )
            cls._detector = cv2.dnn.readNetFromCaffe(str(DETECTOR_PROTOTXT), str(DETECTOR_WEIGHTS))
        return cls._detector

    @classmethod
    def get_embedder(cls):
        raise NotImplementedError("Implemented in Phase 7")

    @classmethod
    def reset(cls) -> None:
        """Test-only: clears the cached model so tests can exercise the
        'weights missing' error path without polluting other tests."""
        cls._detector = None
