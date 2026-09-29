"""
Face detection service (RetinaFace/MTCNN). Implemented in Phase 6.

Planned interface:
    detect_faces(image) -> list[Face]

Where Face carries bounding box, landmarks, and detection confidence.
Kept independent of FastAPI so it's unit-testable on its own.
"""


def detect_faces(image):
    raise NotImplementedError("Implemented in Phase 6")
