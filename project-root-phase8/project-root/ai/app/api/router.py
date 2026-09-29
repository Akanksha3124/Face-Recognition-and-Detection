"""
AI service internal API router. This service has no public port — it's
only reachable from the backend over the internal Docker network (see
infrastructure/docker-compose.yml).
"""
import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.face_detection.detector import DetectedFace, detect_faces
from app.face_embedding.embedder import EMBEDDING_MODEL_VERSION, align_face, generate_embedding
from app.image_quality.quality import assess_quality
from app.schemas.detection import DetectResponse, FaceDetectionOut, QualityMetricsOut
from app.schemas.embedding import EmbedResponse

router = APIRouter()

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB — matches the "secure upload handling" requirement
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
MIN_PROCESSABLE_DIMENSION = 10  # below this, even attempting detection is meaningless
MIN_FACE_CROP_DIMENSION = 20  # below this, resizing up to 112x112 for embedding is mostly noise


def _decode_upload(raw_bytes: bytes) -> np.ndarray:
    """Shared by /detect and /embed — same validation, same error shape."""
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
    return image


def _check_content_type(content_type: str | None) -> None:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported content type: {content_type}. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )


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
    _check_content_type(file.content_type)
    image = _decode_upload(await file.read())

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


@router.post("/embed", response_model=EmbedResponse, tags=["embedding"])
async def embed(
    file: UploadFile = File(...),
    x1: int | None = Form(default=None),
    y1: int | None = Form(default=None),
    x2: int | None = Form(default=None),
    y2: int | None = Form(default=None),
) -> EmbedResponse:
    """
    Phase 7: align a face and generate its embedding.

    Two ways to call this:
    - Just a file: this endpoint runs detection itself and uses the
      result, but only if there's exactly one face — see the "multiple
      faces" case below for why that's a hard requirement rather than
      "use the highest-confidence one."
    - A file plus x1/y1/x2/y2: skips running the detector again,
      embedding exactly the region given. Meant for a caller that
      already called /detect (e.g. to let a human pick one face from a
      photo with several people in it) and knows which box it wants.
    """
    _check_content_type(file.content_type)
    image = _decode_upload(await file.read())
    height, width = image.shape[:2]

    quality = assess_quality(image)
    quality_out = QualityMetricsOut(
        width=quality.width,
        height=quality.height,
        blur_score=quality.blur_score,
        brightness=quality.brightness,
        is_low_resolution=quality.is_low_resolution,
        is_blurry=quality.is_blurry,
        is_too_dark=quality.is_too_dark,
        is_too_bright=quality.is_too_bright,
        passed=quality.passed,
    )

    explicit_box_given = any(coord is not None for coord in (x1, y1, x2, y2))
    if explicit_box_given:
        if None in (x1, y1, x2, y2):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "x1, y1, x2, and y2 must all be provided together, or omitted together",
            )
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Face box out of bounds for a {width}x{height} image",
            )
        face = DetectedFace(x1=x1, y1=y1, x2=x2, y2=y2, confidence=None)
    else:
        try:
            faces = detect_faces(image)
        except RuntimeError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))

        if len(faces) == 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No face detected in image")
        if len(faces) > 1:
            # Deliberately refuse to guess. Silently picking the
            # highest-confidence face in a group photo could enroll or
            # match the wrong person — the kind of mistake this
            # project's human-verification principle exists to avoid
            # even before a match is ever generated.
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"{len(faces)} faces detected; specify which one via x1/y1/x2/y2, or crop before uploading",
            )
        face = faces[0]

    if (face.x2 - face.x1) < MIN_FACE_CROP_DIMENSION or (face.y2 - face.y1) < MIN_FACE_CROP_DIMENSION:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Face region too small to embed reliably",
        )

    try:
        aligned = align_face(image, face)
        embedding = generate_embedding(aligned)
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))

    return EmbedResponse(
        embedding=embedding,
        model_version=EMBEDDING_MODEL_VERSION,
        face_used=FaceDetectionOut(x1=face.x1, y1=face.y1, x2=face.x2, y2=face.y2, confidence=face.confidence),
        quality=quality_out,
    )
