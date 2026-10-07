"""Consent and biometric enrollment for students (FR-A4 to FR-A7, FR-A14).

A student must accept the CURRENT consent version before uploading any
photo or voice clip. Uploads are saved, then a worker job checks quality,
creates embeddings and deletes the raw files.
"""

import uuid

from sqlalchemy import func
from sqlmodel import Session, col, delete, select

from snapclass.core.errors import AppError, bad_request, not_found
from snapclass.core.storage import storage
from snapclass.models import BiometricJob, Consent, ConsentText, FaceEmbedding, User, VoiceEmbedding, utcnow
from snapclass.services.audit import add_audit
from snapclass.services.face_update_service import open_request_for_student
from snapclass.workers.queue import enqueue_enrollment

VOICE_SENTENCE = "Today I am present in class, and I am reading this sentence clearly for SnapClass."
MIN_FACE_PHOTOS, MAX_FACE_PHOTOS = 3, 5
VOICE_CLIPS = 3


def current_consent_text(db: Session) -> ConsentText:
    text = db.exec(select(ConsentText).order_by(col(ConsentText.version).desc())).first()
    if text is None:
        raise not_found("Consent text")
    return text


def active_consent(db: Session, student: User) -> Consent | None:
    """The student's most recent consent that has not been withdrawn."""
    return db.exec(
        select(Consent)
        .where(Consent.student_id == student.id, col(Consent.withdrawn_at).is_(None))
        .order_by(col(Consent.version).desc())
    ).first()


def has_current_consent(db: Session, student: User) -> bool:
    consent = active_consent(db, student)
    return consent is not None and consent.version == current_consent_text(db).version


def accept_consent(db: Session, student: User, version: int) -> None:
    current = current_consent_text(db)
    if version != current.version:
        raise bad_request("Please accept the latest consent text", "CONSENT_OUTDATED")
    existing = db.get(Consent, (student.id, version))
    if existing is None:
        db.add(Consent(student_id=student.id, version=version))
    else:
        existing.granted_at = utcnow()
        existing.withdrawn_at = None
        db.add(existing)
    add_audit(db, student.id, "CONSENT_GRANTED", "user", student.id, after={"version": version})
    db.commit()


def status(db: Session, student: User) -> dict:
    consent = active_consent(db, student)
    face = db.exec(select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.student_id == student.id)).one()
    voice = db.exec(
        select(func.count()).select_from(VoiceEmbedding).where(VoiceEmbedding.student_id == student.id)
    ).one()
    jobs = db.exec(
        select(BiometricJob)
        .where(BiometricJob.student_id == student.id)
        .order_by(col(BiometricJob.created_at).desc())
        .limit(5)
    ).all()
    return {
        "consent_version": consent.version if consent else None,
        "consent_current": has_current_consent(db, student),
        "face_samples": face,
        "voice_samples": voice,
        "jobs": jobs,
        "voice_sentence": VOICE_SENTENCE,
        "face_update_request": open_request_for_student(db, student),
    }


def start_enrollment(db: Session, student: User, kind: str, files: list[tuple[bytes, str]]) -> BiometricJob:
    """Save the uploaded files and queue the enrollment job.

    files: list of (data, extension). kind: "FACE" or "VOICE".
    """
    if not has_current_consent(db, student):
        raise AppError(403, "CONSENT_REQUIRED", "Please accept the consent text first")

    if kind == "FACE" and not MIN_FACE_PHOTOS <= len(files) <= MAX_FACE_PHOTOS:
        raise bad_request(f"Upload {MIN_FACE_PHOTOS} to {MAX_FACE_PHOTOS} photos")
    if kind == "VOICE" and len(files) != VOICE_CLIPS:
        raise bad_request(f"Record exactly {VOICE_CLIPS} voice clips")

    job = BiometricJob(student_id=student.id, kind=kind)
    keys = []
    for data, extension in files:
        key = f"enroll/{student.id}/{job.id}/{uuid.uuid4()}.{extension}"
        storage.save(key, data)
        keys.append(key)

    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        enqueue_enrollment(kind, str(job.id), str(student.id), keys)
    except AppError:
        # Queue is down: do not leave the job "QUEUED" forever, and do not keep the files.
        job.status, job.message, job.finished_at = "FAILED", "Service busy, please try again", utcnow()
        db.add(job)
        db.commit()
        for key in keys:
            storage.delete(key)
        raise
    return job


def erase_biometrics(db: Session, student: User) -> None:
    """FR-A14: delete every embedding and withdraw consent. Attendance history is kept."""
    db.execute(delete(FaceEmbedding).where(col(FaceEmbedding.student_id) == student.id))
    db.execute(delete(VoiceEmbedding).where(col(VoiceEmbedding.student_id) == student.id))
    for consent in db.exec(select(Consent).where(Consent.student_id == student.id)).all():
        consent.withdrawn_at = consent.withdrawn_at or utcnow()
        db.add(consent)
    add_audit(db, student.id, "BIOMETRIC_DELETE", "user", student.id)
    db.commit()
