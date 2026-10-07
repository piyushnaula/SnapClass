"""Load each ML model once per worker process and reuse it for every job."""

from functools import lru_cache

from snapclass.core.config import settings


@lru_cache
def get_face_encoder():  # noqa: ANN201
    from snapclass.ml.face import OpenCVFaceEncoder

    return OpenCVFaceEncoder(settings.face_detector_path, settings.face_recognizer_path)


@lru_cache
def get_voice_embedder():  # noqa: ANN201
    from snapclass.ml.voice import VoiceEmbedder

    return VoiceEmbedder()
