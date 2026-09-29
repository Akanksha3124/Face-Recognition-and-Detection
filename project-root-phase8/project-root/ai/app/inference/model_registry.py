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
import onnxruntime as ort

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
DETECTOR_PROTOTXT = MODELS_DIR / "face_detection" / "deploy.prototxt"
DETECTOR_WEIGHTS = MODELS_DIR / "face_detection" / "res10_300x300_ssd_iter_140000.caffemodel"
EMBEDDER_WEIGHTS = MODELS_DIR / "face_embedding" / "w600k_mbf.onnx"


class ModelRegistry:
    _detector = None
    _embedder = None

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
    def get_embedder(cls) -> ort.InferenceSession:
        if cls._embedder is None:
            if not EMBEDDER_WEIGHTS.exists():
                raise RuntimeError(
                    "Face embedding weights not found. From the ai/ directory, run: "
                    "python scripts/download_models.py "
                    f"(expected file at {EMBEDDER_WEIGHTS})"
                )
            # CPU-only by design (see embedder.py) — this project targets
            # a student development machine, not a GPU server.
            cls._embedder = ort.InferenceSession(
                str(EMBEDDER_WEIGHTS), providers=["CPUExecutionProvider"]
            )
        return cls._embedder

    @classmethod
    def reset(cls) -> None:
        """Test-only: clears cached models so tests can exercise the
        'weights missing' error path without polluting other tests."""
        cls._detector = None
        cls._embedder = None
