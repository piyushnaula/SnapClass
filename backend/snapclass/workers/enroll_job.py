"""Enrollment jobs: quality checks → embeddings → delete raw files (FR-A5, FR-A6, FR-A7).

Quality rules (spec A.9.7):
* exactly one face per photo
* face at least 80 px on its shortest side
* sharp enough (variance of Laplacian above a threshold)
* voice: at least 3 seconds of detected speech per clip
"""

import logging
import uuid

import numpy as np
from sqlalchemy import text
from sqlmodel import Session, col, delete

from snapclass.core.config import settings
from snapclass.core.db import engine
from snapclass.core.storage import storage
from snapclass.ml.face import decode_image
from snapclass.ml.voice import decode_audio, speech_seconds
from snapclass.models import BiometricJob, FaceEmbedding, User, VoiceEmbedding, utcnow
from snapclass.services.audit import add_audit
from snapclass.services.biometric_service import has_current_consent
from snapclass.services.face_update_service import resolve_for_student
from snapclass.services.settings_service import get_setting
from snapclass.workers.models_cache import get_face_encoder, get_voice_embedder

logger = logging.getLogger(__name__)

MIN_GOOD_PHOTOS = 3
MIN_SPEECH_SECONDS = 3.0
# Another student's face closer than this (L2) is suspicious: maybe a duplicate account.
DUPLICATE_DISTANCE = 0.9


def _finish(db: Session, job: BiometricJob, status: str, message: str) -> None:
    job.status = status
    job.message = message
    job.finished_at = utcnow()
    db.add(job)


def _cleanup(keys: list[str]) -> None:
    if settings.delete_enrollment_media:
        for key in keys:
            storage.delete(key)


def check_face_photo(data: bytes, min_face_px: int, blur_threshold: float):  # noqa: ANN201
    """Return (face, None) if the photo passes every check, else (None, message for the student)."""
    image = decode_image(data)
    if image is None:
        return None, "File could not be read as an image"
    faces = get_face_encoder().encode(image, min_face_px=20)
    if len(faces) == 0:
        return None, "No face found. Face the camera in good light"
    if len(faces) > 1:
        return None, "Make sure only your face is in the photo"
    face = faces[0]
    left, top, right, bottom = face.box
    if min(right - left, bottom - top) < min_face_px:
        return None, "Move closer to the camera"
    if face.sharpness < blur_threshold:
        return None, "Photo is blurry, hold steady"
    return face, None


def _consent_still_valid(db: Session, student_id: str) -> bool:
    """The student may have withdrawn consent while the job was waiting in the queue."""
    student = db.get(User, uuid.UUID(student_id))
    return student is not None and has_current_consent(db, student)


def enroll_face(job_id: str, student_id: str, keys: list[str]) -> None:
    with Session(engine) as db:
        job = db.get(BiometricJob, uuid.UUID(job_id))
        if job is None or job.status != "QUEUED":
            return  # duplicate or late job → nothing to do
        rules = get_setting(db, "enrollment")

    good_faces, problems = [], []
    for number, key in enumerate(keys, start=1):
        face, problem = check_face_photo(storage.read(key), int(rules["min_face_px"]), float(rules["blur_threshold"]))
        if face is None:
            problems.append(f"Photo {number}: {problem}")
        else:
            good_faces.append(face)

    with Session(engine) as db:
        job = db.get(BiometricJob, uuid.UUID(job_id))
        assert job is not None
        if not _consent_still_valid(db, student_id):
            _finish(db, job, "FAILED", "Consent was withdrawn, nothing was saved.")
            db.commit()
            _cleanup(keys)
            return
        if len(good_faces) < MIN_GOOD_PHOTOS:
            needed = f"Need at least {MIN_GOOD_PHOTOS} good photos, got {len(good_faces)}."
            _finish(db, job, "FAILED", needed + " " + "; ".join(problems) + ".")
            db.commit()
            _cleanup(keys)
            return

        student_uuid = uuid.UUID(student_id)
        # Re-enrolling replaces the old embeddings (same transaction).
        db.execute(delete(FaceEmbedding).where(col(FaceEmbedding.student_id) == student_uuid))
        model_version = get_face_encoder().model_version
        for face in good_faces:
            db.add(
                FaceEmbedding(
                    student_id=student_uuid, embedding=face.embedding, quality=face.quality, model_ver=model_version
                )
            )

        duplicate = find_duplicate_face(db, student_uuid, good_faces[0].embedding)
        if duplicate:
            add_audit(db, None, "DUPLICATE_FACE_SUSPECTED", "user", student_id, after=duplicate)

        message = f"Saved {len(good_faces)} face samples."
        # New photos accepted → the teacher's "please upload a new photo" request is done.
        if resolve_for_student(db, student_uuid):
            message += " Your teacher's request for a new photo is complete."
        if problems:
            message += " Skipped: " + "; ".join(problems)
        _finish(db, job, "DONE", message)
        db.commit()
    _cleanup(keys)
    logger.info("Face enrollment done", extra={"fields": {"student_id": student_id, "samples": len(good_faces)}})


def find_duplicate_face(db: Session, student_id: uuid.UUID, embedding: np.ndarray) -> dict | None:
    """Nearest face of a DIFFERENT student across the whole institution (uses the HNSW index)."""
    row = db.execute(
        text(
            """
            SELECT student_id, embedding <-> CAST(:emb AS vector) AS distance
            FROM face_embeddings
            WHERE student_id <> :student_id
            ORDER BY embedding <-> CAST(:emb AS vector)
            LIMIT 1
            """
        ),
        {"emb": str(embedding.tolist()), "student_id": student_id},
    ).first()
    if row is not None and row.distance < DUPLICATE_DISTANCE:
        return {"similar_to_student_id": str(row.student_id), "distance": round(float(row.distance), 3)}
    return None


def enroll_voice(job_id: str, student_id: str, keys: list[str]) -> None:
    with Session(engine) as db:
        job = db.get(BiometricJob, uuid.UUID(job_id))
        if job is None or job.status != "QUEUED":
            return

    embeddings, problems = [], []
    embedder = get_voice_embedder()
    for number, key in enumerate(keys, start=1):
        try:
            wav = decode_audio(storage.read(key), max_seconds=15)
        except ValueError:
            problems.append(f"Clip {number}: could not read the recording")
            continue
        if speech_seconds(wav) < MIN_SPEECH_SECONDS:
            problems.append(f"Clip {number}: please read the full sentence")
            continue
        embeddings.append(embedder.embed(wav))

    with Session(engine) as db:
        job = db.get(BiometricJob, uuid.UUID(job_id))
        assert job is not None
        if not _consent_still_valid(db, student_id):
            _finish(db, job, "FAILED", "Consent was withdrawn, nothing was saved.")
        elif problems:
            _finish(db, job, "FAILED", "; ".join(problems) + ".")
        else:
            student_uuid = uuid.UUID(student_id)
            db.execute(delete(VoiceEmbedding).where(col(VoiceEmbedding.student_id) == student_uuid))
            for embedding in embeddings:
                db.add(VoiceEmbedding(student_id=student_uuid, embedding=embedding, model_ver=embedder.model_version))
            _finish(db, job, "DONE", f"Saved {len(embeddings)} voice samples.")
        db.commit()
    _cleanup(keys)
