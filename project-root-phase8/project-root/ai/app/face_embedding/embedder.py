"""
Face embedding generation.

Model choice — insightface's "buffalo_s" recognition model
(w600k_mbf.onnx, MobileFaceNet-based ArcFace), not the ResNet100 ArcFace
model the ONNX Model Zoo ships. Why: the zoo's model is ~249MB; this one
is ~14MB and runs comfortably on CPU — the same "student machine,
CPU-only" reasoning Phase 6 used to pick its detector. Real accuracy
trade-off worth knowing: MobileFaceNet trades some accuracy for that
size/speed, particularly under the harder conditions this whole project
cares about (age gap, disguise, low quality). If Phase 11/12's
evaluation numbers look weak, swapping in the larger w600k_r50.onnx
(same buffalo family, ResNet50, ~166MB) is a drop-in change — same
112x112 input, same 512-d output, same preprocessing.

Known limitation carried over from Phase 6, worth repeating here: the
detector provides bounding boxes only, no facial landmarks. Real
ArcFace pipelines use 5-point landmarks for a similarity-transform
alignment (rotating/scaling the face into a canonical pose) before
embedding — that's what "align_face" usually means. Without landmarks,
`align_face` below is a plain crop-and-resize, not a landmark-aligned
warp. This is the most likely source of avoidable accuracy loss in the
current pipeline; revisit together with the detector choice if
Phase 11/12 numbers justify it.
"""
import cv2
import numpy as np

from app.face_detection.detector import DetectedFace, crop_face
from app.inference.model_registry import ModelRegistry

EMBEDDING_DIM = 512
EMBEDDING_MODEL_VERSION = "insightface-buffalo_s/w600k_mbf"

_INPUT_SIZE = (112, 112)  # what this ArcFace variant was trained on


def align_face(image: np.ndarray, face: DetectedFace) -> np.ndarray:
    """
    Crop the detected face and resize to the embedding model's expected
    112x112 input. NOT a landmark-based alignment — see the module
    docstring for why, and what a real fix would look like.
    """
    crop = crop_face(image, face, margin_ratio=0.2)
    return cv2.resize(crop, _INPUT_SIZE)


def _preprocess(aligned_image: np.ndarray) -> np.ndarray:
    """BGR HWC uint8 -> RGB CHW float32 batch of 1, normalized to
    [-1, 1] — the standard ArcFace preprocessing recipe this model was
    trained with (mean=127.5, std=127.5)."""
    rgb = cv2.cvtColor(aligned_image, cv2.COLOR_BGR2RGB)
    normalized = (rgb.astype(np.float32) - 127.5) / 127.5
    chw = np.transpose(normalized, (2, 0, 1))
    return np.expand_dims(chw, axis=0)


def generate_embedding(aligned_image: np.ndarray) -> list[float]:
    """
    aligned_image: a 112x112 BGR image, as returned by align_face().
    Returns a 512-d L2-normalized embedding — normalized because the
    backend stores these in pgvector and compares them with cosine
    distance (see backend/app/models/face_embedding.py), and a
    normalized vector makes cosine and dot-product comparisons
    equivalent, which is a common convention worth keeping explicit
    rather than relying on every future caller to remember it.
    """
    session = ModelRegistry.get_embedder()
    input_name = session.get_inputs()[0].name
    batch = _preprocess(aligned_image)
    raw_embedding = session.run(None, {input_name: batch})[0][0]

    norm = np.linalg.norm(raw_embedding)
    normalized = raw_embedding / norm if norm > 0 else raw_embedding
    return normalized.tolist()
