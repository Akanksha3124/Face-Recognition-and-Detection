"""
AI service internal API router. This service has no public port — it's
only reachable from the backend over the internal Docker network (see
infrastructure/docker-compose.yml).
"""
import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.face_detection.detector import detect_faces
from app.image_quality.quality import assess_quality
from app.schemas.detection import DetectResponse, FaceDetectionOut, QualityMetricsOut

router = APIRouter()

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB — matches the "secure upload handling" requirement
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
MIN_PROCESSABLE_DIMENSION = 10  # below this, even attempting detection is meaningless


@router.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "service": "ai"}


@router.post("/detect", response_model=DetectResponse, tags=["detection"])
async def detect(file: UploadFile = File(...)) -> DetectResponse:
    """
    Phase 6: image validation -> quality assessment -> face detection.
    Returns quality metrics unconditionally (even a low-quality image
    still gets a quality report) plus whatever faces clear the
    detector's confidence threshold — zero faces is a valid, non-error
    response; the caller decides what to do with an empty list.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported content type: {file.content_type}. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Image exceeds the {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB limit",
        )
    if len(raw_bytes) == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Uploaded file is empty")

    image_array = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Could not decode image — file may be corrupt or not a valid JPEG/PNG",
        )

    quality = assess_quality(image)
    if quality.width < MIN_PROCESSABLE_DIMENSION or quality.height < MIN_PROCESSABLE_DIMENSION:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Image resolution too low to process")

    try:
        faces = detect_faces(image)
    except RuntimeError as exc:
        # Model weights not downloaded — see model_registry.py. This is
        # a deployment/setup problem, not a bad request, hence 503.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))

    return DetectResponse(
        quality=QualityMetricsOut(
            width=quality.width,
            height=quality.height,
            blur_score=quality.blur_score,
            brightness=quality.brightness,
            is_low_resolution=quality.is_low_resolution,
            is_blurry=quality.is_blurry,
            is_too_dark=quality.is_too_dark,
            is_too_bright=quality.is_too_bright,
            passed=quality.passed,
        ),
        faces=[
            FaceDetectionOut(x1=f.x1, y1=f.y1, x2=f.x2, y2=f.y2, confidence=f.confidence) for f in faces
        ],
    )
