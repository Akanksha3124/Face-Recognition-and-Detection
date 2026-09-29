"""
Face embedding generation (ArcFace/InsightFace). Implemented in Phase 7.

Planned interface:
    align_face(image, landmarks) -> aligned_image
    generate_embedding(aligned_image) -> 512-d vector (L2-normalized)

The model is loaded once at process startup (see app/inference/) and
reused across requests — never reloaded per request.
"""


def align_face(image, landmarks):
    raise NotImplementedError("Implemented in Phase 7")


def generate_embedding(aligned_image):
    raise NotImplementedError("Implemented in Phase 7")
