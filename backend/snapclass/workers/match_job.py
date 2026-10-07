"""The match job: class photos/audio → proposed attendance (spec A.9.6).

Why two database transactions?
  Downloading files and running the models takes seconds. If we kept the
  session row locked the whole time, other requests would wait. So:
    1. Transaction 1: lock the session, read the roster, release the lock.
    2. Slow work with no transaction open.
    3. Transaction 2: lock again, CHECK THE STATUS AGAIN, write results.
  The second status check makes duplicate or late jobs harmless (idempotent).
"""

import logging
import time
import uuid
from collections import defaultdict

import numpy as np
from sqlmodel import Session, col, delete, select

from snapclass.core.db import engine
from snapclass.core.storage import storage
from snapclass.domain.decisions import Decision, Thresholds, decide
from snapclass.domain.session import SessionStatus, check_transition
from snapclass.ml.face import crop_face, decode_image
from snapclass.ml.matcher import RosterMatcher, best_unassigned_distance, one_to_one_assign
from snapclass.ml.voice import VOICE_MODEL_VERSION, decode_audio
from snapclass.models import (
    AttendanceSession,
    Enrollment,
    FaceEmbedding,
    MatchResult,
    SessionMedia,
    UnmatchedFace,
    VoiceEmbedding,
    utcnow,
)
from snapclass.services.face_update_service import open_request_ids
from snapclass.workers.models_cache import get_face_encoder, get_voice_embedder

logger = logging.getLogger(__name__)

SESSION_MIN_FACE_PX = 24  # class photos: back-row faces are small


# ---------- Loading data (inside transaction 1) ----------


def _lock_session(db: Session, session_id: uuid.UUID) -> AttendanceSession | None:
    return db.exec(select(AttendanceSession).where(AttendanceSession.id == session_id).with_for_update()).first()


def _enrolled_ids(db: Session, class_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.exec(select(Enrollment.student_id).where(Enrollment.class_id == class_id)).all())


def load_face_roster(db: Session, class_id: uuid.UUID, model_version: str) -> dict[str, np.ndarray]:
    """{student_id: (k, 128) matrix} for students of THIS class only (roster-restricted matching).
    Only embeddings from the current model version are comparable."""
    rows = db.exec(
        select(FaceEmbedding.student_id, FaceEmbedding.embedding)
        .join(Enrollment, Enrollment.student_id == FaceEmbedding.student_id)
        .where(Enrollment.class_id == class_id, FaceEmbedding.model_ver == model_version)
    ).all()
    grouped: dict[str, list[np.ndarray]] = defaultdict(list)
    for student_id, embedding in rows:
        grouped[str(student_id)].append(np.asarray(embedding, dtype=np.float32))
    return {sid: np.stack(vectors) for sid, vectors in grouped.items()}


def load_voice_roster(db: Session, class_id: uuid.UUID) -> dict[str, np.ndarray]:
    """{student_id: mean voice embedding (unit length)} for students of this class."""
    rows = db.exec(
        select(VoiceEmbedding.student_id, VoiceEmbedding.embedding)
        .join(Enrollment, Enrollment.student_id == VoiceEmbedding.student_id)
        .where(Enrollment.class_id == class_id)
    ).all()
    grouped: dict[str, list[np.ndarray]] = defaultdict(list)
    for student_id, embedding in rows:
        grouped[str(student_id)].append(np.asarray(embedding, dtype=np.float32))
    roster = {}
    for sid, vectors in grouped.items():
        mean = np.mean(vectors, axis=0)
        roster[sid] = mean / np.linalg.norm(mean)
    return roster


# ---------- Slow work (no transaction open) ----------


def match_faces(photos: list[bytes], roster: dict[str, np.ndarray], t: Thresholds, session_id: str):  # noqa: ANN201
    """Returns (best distance per student, crop key per student, unmatched faces [(crop_key, distance)])."""
    encoder = get_face_encoder()
    matcher = RosterMatcher(roster)
    # A new check replaces the face crops of any earlier check of this lecture.
    storage.delete_folder(f"crops/{session_id}/")
    best_distance: dict[str, float] = {}
    best_crop: dict[str, bytes] = {}
    unmatched: list[tuple[bytes, float | None]] = []

    for data in photos:
        image = decode_image(data)
        if image is None:
            logger.warning("Skipping unreadable photo", extra={"fields": {"session_id": session_id}})
            continue
        faces = encoder.encode(image, min_face_px=SESSION_MIN_FACE_PX)
        if not faces:
            continue
        probes = np.stack([face.embedding for face in faces])

        # Each photo is assigned on its own (one face ↔ one student per photo).
        assigned_faces = set()
        for face_index, student_id, distance in matcher.assign(probes, reject_above=t.face_reject):
            assigned_faces.add(face_index)
            # Across photos keep the SMALLEST distance: one clear view is enough.
            if distance < best_distance.get(student_id, float("inf")):
                best_distance[student_id] = distance
                best_crop[student_id] = crop_face(image, faces[face_index].box)

        for face_index, face in enumerate(faces):
            if face_index not in assigned_faces:
                unmatched.append((crop_face(image, face.box), best_unassigned_distance(matcher, face.embedding)))

    crop_keys = {}
    for student_id, crop in best_crop.items():
        key = f"crops/{session_id}/{student_id}.jpg"
        storage.save(key, crop)
        crop_keys[student_id] = key
    unmatched_keys = []
    for number, (crop, distance) in enumerate(unmatched):
        key = f"crops/{session_id}/unmatched-{number}.jpg"
        storage.save(key, crop)
        unmatched_keys.append((key, distance))
    return best_distance, crop_keys, unmatched_keys


def match_voice(audio: bytes, roster: dict[str, np.ndarray], t: Thresholds) -> dict[str, float]:
    """Returns the best cosine similarity per student who was heard."""
    if not roster:
        return {}
    windows = get_voice_embedder().embed_windows(decode_audio(audio, max_seconds=60))
    if not windows:
        return {}
    student_ids = list(roster)
    gallery = np.stack([roster[sid] for sid in student_ids])  # (n_students, 256)
    similarity = np.stack(windows) @ gallery.T  # cosine, because all vectors have length 1
    # Same one-to-one assignment as faces, using distance = 1 - similarity.
    pairs = one_to_one_assign(1.0 - similarity, reject_above=1.0 - t.voice_reject)
    return {student_ids[col]: round(1.0 - distance, 4) for _, col, distance in pairs}


# ---------- The job ----------


def run_match(session_id: str) -> None:
    started = time.monotonic()
    sid = uuid.UUID(session_id)
    face_model = get_face_encoder().model_version

    # Transaction 1: read everything we need, then release the lock.
    with Session(engine) as db:
        session = _lock_session(db, sid)
        if session is None or session.status != SessionStatus.PROCESSING:
            logger.info("Match job skipped", extra={"fields": {"session_id": session_id}})
            return
        thresholds = Thresholds.from_dict(session.config_snapshot["thresholds"])
        face_roster = load_face_roster(db, session.class_id, face_model)
        voice_roster = load_voice_roster(db, session.class_id)
        has_samples = set(face_roster) | set(voice_roster)
        # A teacher asked these students for a new face photo, so their old photos are
        # not trusted: leave them out of matching (never marked present automatically).
        pending = {str(s) for s in open_request_ids(db, _enrolled_ids(db, session.class_id))}
        face_roster = {sid: emb for sid, emb in face_roster.items() if sid not in pending}
        voice_roster = {sid: emb for sid, emb in voice_roster.items() if sid not in pending}
        media = db.exec(
            select(SessionMedia).where(SessionMedia.session_id == sid, col(SessionMedia.deleted_at).is_(None))
        ).all()
        photo_keys = [m.object_key for m in media if m.kind == "PHOTO"]
        audio_keys = [m.object_key for m in media if m.kind == "AUDIO"]

    # Slow part: no database transaction is open here.
    photos = [storage.read(key) for key in photo_keys]
    face_best, crop_keys, unmatched = match_faces(photos, face_roster, thresholds, session_id)
    voice_best = match_voice(storage.read(audio_keys[0]), voice_roster, thresholds) if audio_keys else {}

    # Transaction 2: check the status again, then write all results at once.
    with Session(engine) as db:
        session = _lock_session(db, sid)
        if session is None or session.status != SessionStatus.PROCESSING:
            return  # someone else finished this session already

        # Checking again (after adding photos) must not throw away the teacher's own choices.
        teacher_choices = {
            r.student_id: r.teacher_decision
            for r in db.exec(select(MatchResult).where(MatchResult.session_id == sid)).all()
            if r.teacher_decision
        }
        db.execute(delete(MatchResult).where(col(MatchResult.session_id) == sid))
        db.execute(delete(UnmatchedFace).where(col(UnmatchedFace.session_id) == sid))

        for student_uuid in _enrolled_ids(db, session.class_id):
            student_id = str(student_uuid)
            has_biometrics = student_id in has_samples
            update_pending = student_id in pending
            face_distance = face_best.get(student_id)
            voice_score = voice_best.get(student_id)
            if has_biometrics and not update_pending:
                decision, score = decide(face_distance, voice_score, thresholds)
            else:
                decision, score = Decision.NOT_DETECTED, None
            db.add(
                MatchResult(
                    session_id=sid,
                    student_id=student_uuid,
                    decision=decision.value,
                    face_distance=None if face_distance is None else round(face_distance, 4),
                    voice_score=voice_score,
                    fused_score=None if score is None else round(score, 4),
                    crop_key=crop_keys.get(student_id),
                    has_biometrics=has_biometrics,
                    face_update_pending=update_pending,
                    teacher_decision=teacher_choices.get(student_uuid),
                )
            )
        for key, distance in unmatched:
            db.add(
                UnmatchedFace(
                    session_id=sid, crop_key=key, best_distance=None if distance is None else round(distance, 4)
                )
            )

        check_transition(session.status, SessionStatus.REVIEW)
        session.status = SessionStatus.REVIEW.value
        # Measure from "teacher pressed process" (includes queue wait), the number the NFR is about.
        if session.processing_started_at is not None:
            session.processing_ms = int((utcnow() - session.processing_started_at).total_seconds() * 1000)
        else:
            session.processing_ms = int((time.monotonic() - started) * 1000)
        session.config_snapshot = {
            **session.config_snapshot,
            "models": {"face": face_model, "voice": VOICE_MODEL_VERSION},
        }
        db.add(session)
        db.commit()

    logger.info(
        "Match job done",
        extra={
            "fields": {"session_id": session_id, "faces_matched": len(face_best), "voices_matched": len(voice_best)}
        },
    )
