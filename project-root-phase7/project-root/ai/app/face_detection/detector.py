"""
Face detection service.

Model choice — OpenCV's SSD ResNet-10 Caffe face detector, not
RetinaFace/MTCNN as the architecture doc originally suggested. Why:
this model needs only OpenCV (already a dependency) rather than
PyTorch/TensorFlow + a much heavier model download, runs comfortably on
a CPU-only student machine, and is a well-established, widely-used
pretrained detector (it ships with OpenCV's own official samples). This
is a deliberate scope decision for Phase 6, not an oversight.

Known limitation worth carrying into Phase 7: this model outputs only
bounding boxes and a confidence score — no facial landmarks (eyes,
nose, mouth). RetinaFace/MTCNN provide 5-point landmarks, which is what
you'd normally use for precise, rotation-corrected face alignment
before generating an ArcFace embedding. Phase 6's `crop_face()` below
is therefore a simple margin-padded rectangular crop, not a landmark-
aligned one. If Phase 7's embedding accuracy suffers without proper
alignment, swapping in a landmark-capable detector (e.g. via
insightface's bundled RetinaFace/SCRFD) is the fix — this module's
`detect_faces()` interface is intentionally the only thing callers
depend on, so that swap wouldn't ripple through the codebase.
"""
from dataclasses import dataclass

import cv2
import numpy as np

from app.inference.model_registry import ModelRegistry

# Below this confidence, a "detection" is more likely noise than a real
# face — this is the "reject extremely poor detections" requirement.
# Heuristic default, not tuned against a labeled dataset; revisit
# alongside the Phase 11/12 evaluation work if false positives/negatives
# turn out to be a problem in practice.
DEFAULT_MIN_CONFIDENCE = 0.5

_DETECTOR_INPUT_SIZE = (300, 300)
_MEAN_SUBTRACTION = (104.0, 177.0, 123.0)  # values the model was trained with


@dataclass
class DetectedFace:
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float | None = None


def detect_faces(image: np.ndarray, min_confidence: float = DEFAULT_MIN_CONFIDENCE) -> list[DetectedFace]:
    """
    image: a BGR image as returned by cv2.imread/cv2.imdecode.
    Returns faces sorted by confidence, descending. Handles zero, one,
    or multiple faces — callers decide what an empty list means for
    their use case (this module doesn't treat "no face" as an error).
    """
    net = ModelRegistry.get_detector()
    height, width = image.shape[:2]

    blob = cv2.dnn.blobFromImage(
        cv2.resize(image, _DETECTOR_INPUT_SIZE), 1.0, _DETECTOR_INPUT_SIZE, _MEAN_SUBTRACTION
    )
    net.setInput(blob)
    raw_detections = net.forward()

    faces: list[DetectedFace] = []
    for i in range(raw_detections.shape[2]):
        confidence = float(raw_detections[0, 0, i, 2])
        if confidence < min_confidence:
            continue

        box = raw_detections[0, 0, i, 3:7] * np.array([width, height, width, height])
        x1, y1, x2, y2 = box.astype(int)
        # The model can output coordinates slightly outside the frame
        # near edges — clip rather than let a downstream crop crash.
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width, x2), min(height, y2)
        if x2 <= x1 or y2 <= y1:
            continue  # degenerate box after clipping — skip it

        faces.append(DetectedFace(x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2), confidence=confidence))

    faces.sort(key=lambda f: f.confidence, reverse=True)
    return faces


def crop_face(image: np.ndarray, face: DetectedFace, margin_ratio: float = 0.2) -> np.ndarray:
    """
    Rectangular crop around a detected face with a margin — NOT a
    landmark-aligned crop (see the module docstring). Fine for a
    preview thumbnail; Phase 7 will need real alignment before feeding
    a crop into an embedding model.
    """
    height, width = image.shape[:2]
    box_width = face.x2 - face.x1
    box_height = face.y2 - face.y1
    margin_x = int(box_width * margin_ratio)
    margin_y = int(box_height * margin_ratio)

    x1 = max(0, face.x1 - margin_x)
    y1 = max(0, face.y1 - margin_y)
    x2 = min(width, face.x2 + margin_x)
    y2 = min(height, face.y2 + margin_y)
    return image[y1:y2, x1:x2]
