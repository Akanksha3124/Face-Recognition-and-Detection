from pydantic import BaseModel


class FaceDetectionOut(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    # None when the caller supplied this box directly (POST /embed with
    # explicit x1/y1/x2/y2) rather than it coming from detect_faces(),
    # which always sets a real confidence score.
    confidence: float | None = None


class QualityMetricsOut(BaseModel):
    width: int
    height: int
    blur_score: float
    brightness: float
    is_low_resolution: bool
    is_blurry: bool
    is_too_dark: bool
    is_too_bright: bool
    passed: bool


class DetectResponse(BaseModel):
    quality: QualityMetricsOut
    faces: list[FaceDetectionOut]
