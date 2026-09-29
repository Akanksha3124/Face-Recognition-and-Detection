from pydantic import BaseModel, ConfigDict

from app.schemas.detection import FaceDetectionOut, QualityMetricsOut


class EmbedResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    embedding: list[float]
    model_version: str
    face_used: FaceDetectionOut
    quality: QualityMetricsOut
