"""
Model loading and singleton cache.
Ensures each model (detector, embedder) is loaded exactly once at
process startup and reused across requests — never per-request.
Populated in Phase 6-7 alongside the detector/embedder implementations.
"""


class ModelRegistry:
    _detector = None
    _embedder = None

    @classmethod
    def get_detector(cls):
        if cls._detector is None:
            raise NotImplementedError("Model loading implemented in Phase 6")
        return cls._detector

    @classmethod
    def get_embedder(cls):
        if cls._embedder is None:
            raise NotImplementedError("Model loading implemented in Phase 7")
        return cls._embedder
