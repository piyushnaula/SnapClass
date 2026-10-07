"""Attendance sessions: create, upload, process, review, finalize, correct (FR-A8 to FR-A12)."""

import hashlib
import uuid
from datetime import date

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from snapclass.core.errors import AppError, bad_request, conflict, not_found
from snapclass.core.security import signed_media_url
from snapclass.core.storage import storage
from snapclass.domain.session import (
    InvalidTransition,
    SessionStatus,
    can_change_media,
    check_transition,
    status_after_media_change,
)
from snapclass.models import (
    AttendanceRecord,
    AttendanceSession,
    Classroom,
    MatchResult,
    SessionMedia,
    UnmatchedFace,
    User,
    utcnow,
)
from snapclass.services.audit import add_audit
from snapclass.services.face_update_service import open_request_ids
from snapclass.services.settings_service import get_setting
from snapclass.workers.queue import enqueue_match, match_job_id

MAX_PHOTOS = 10  # class photos per lecture (raised from the spec's 4 for large rooms)
MAX_AUDIO = 1


def set_status(session: AttendanceSession, target: SessionStatus) -> None:
    """Every status change goes through the state machine."""
    try:
        check_transition(session.status, target)
    except InvalidTransition as exc:
        raise conflict(str(exc), "INVALID_TRANSITION") from exc
    session.status = target.value


def get_owned_session(db: Session, session_id: uuid.UUID, teacher: User, for_update: bool = False) -> AttendanceSession:
    """Load a session only if this teacher owns it (404 otherwise).

    for_update=True locks the row (SELECT ... FOR UPDATE) so two requests
    cannot change the same session at the same time.
    """
    query = select(AttendanceSession).where(
        AttendanceSession.id == session_id, AttendanceSession.teacher_id == teacher.id
    )
    if for_update:
        query = query.with_for_update()
    session = db.exec(query).first()
    if session is None:
        raise not_found("Session")
    return session


def _config_snapshot(db: Session) -> dict:
    return {"thresholds": get_setting(db, "thresholds"), "enrollment": get_setting(db, "enrollment")}


def create_session(
    db: Session, teacher: User, classroom: Classroom, session_date: date, period: int
) -> AttendanceSession:
    session = AttendanceSession(
        class_id=classroom.id,
        teacher_id=teacher.id,
        session_date=session_date,
        period=period,
        config_snapshot=_config_snapshot(db),
    )
    db.add(session)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("A session for this class, date and period already exists") from None
    db.refresh(session)
    return session


def list_sessions(db: Session, classroom: Classroom) -> list[AttendanceSession]:
    return list(
        db.exec(
            select(AttendanceSession)
            .where(AttendanceSession.class_id == classroom.id)
            .order_by(col(AttendanceSession.session_date).desc(), col(AttendanceSession.period).desc())
        ).all()
    )


def _media(db: Session, session_id: uuid.UUID) -> list[SessionMedia]:
    return list(db.exec(select(SessionMedia).where(SessionMedia.session_id == session_id)).all())


def add_media(
    db: Session, teacher: User, session_id: uuid.UUID, photos: list[tuple[bytes, str]], audio: bytes | None
) -> None:
    """Save class photos (up to 10) and/or one audio clip.

    Also works during review (or after a failed check): the teacher adds photos,
    and the session goes back to "photos added" until it is checked again.
    """
    session = get_owned_session(db, session_id, teacher, for_update=True)
    _ensure_media_can_change(session)

    existing = _media(db, session_id)
    photo_count = sum(1 for m in existing if m.kind == "PHOTO") + len(photos)
    audio_count = sum(1 for m in existing if m.kind == "AUDIO") + (1 if audio else 0)
    if photo_count > MAX_PHOTOS:
        raise bad_request(f"A session can have at most {MAX_PHOTOS} photos")
    if audio_count > MAX_AUDIO:
        raise bad_request("A session can have only one audio clip")
    if not photos and not audio:
        raise bad_request("Upload at least one photo or audio clip")

    uploads = [(data, ext, "PHOTO") for data, ext in photos]
    if audio:
        uploads.append((audio, "audio", "AUDIO"))
    for data, extension, kind in uploads:
        key = f"sessions/{session.id}/{uuid.uuid4()}.{extension}"
        storage.save(key, data)
        db.add(
            SessionMedia(
                session_id=session.id,
                kind=kind,
                object_key=key,
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
            )
        )

    _move_after_media_change(session, has_media=True)
    db.add(session)
    db.commit()


def _ensure_media_can_change(session: AttendanceSession) -> None:
    if session.status == SessionStatus.PROCESSING:
        raise conflict("The photos are being checked right now. Please wait a few seconds.", "MEDIA_LOCKED")
    if not can_change_media(session.status):
        raise conflict('Attendance is already saved. Use "Change" next to a student instead.', "MEDIA_LOCKED")


def _move_after_media_change(session: AttendanceSession, has_media: bool) -> None:
    """New or removed photos mean the old check is out of date: wait for a new check."""
    target = status_after_media_change(has_media)
    if session.status != target:
        set_status(session, target)


def remove_media(db: Session, teacher: User, session_id: uuid.UUID, media_id: uuid.UUID) -> None:
    """Delete one uploaded photo or audio clip (for example a blurry photo)."""
    session = get_owned_session(db, session_id, teacher, for_update=True)
    _ensure_media_can_change(session)
    item = db.get(SessionMedia, media_id)
    if item is None or item.session_id != session.id:
        raise not_found("Photo")
    storage.delete(item.object_key)
    db.delete(item)
    db.flush()
    _move_after_media_change(session, has_media=len(_media(db, session.id)) > 0)
    db.add(session)
    db.commit()


def _verify_media(media: list[SessionMedia]) -> None:
    """Make sure every uploaded file still exists and is unchanged before queuing."""
    for item in media:
        if not storage.exists(item.object_key):
            raise conflict("An uploaded file is missing, please upload again", "MEDIA_MISSING")
        if hashlib.sha256(storage.read(item.object_key)).hexdigest() != item.sha256:
            raise conflict("An uploaded file is corrupted, please upload again", "MEDIA_CORRUPTED")


def start_processing(
    db: Session, teacher: User, session_id: uuid.UUID, clear_decisions: bool = False
) -> tuple[AttendanceSession, bool]:
    """Queue the match job. Idempotent: calling it twice never queues twice.

    When the photos are checked again, the teacher's Present/Absent choices are
    kept (never thrown away silently) unless clear_decisions=True.
    Returns (session, queued_now).
    """
    session = get_owned_session(db, session_id, teacher, for_update=True)
    if session.status in (SessionStatus.PROCESSING, SessionStatus.REVIEW, SessionStatus.FINALIZED):
        return session, False  # already done or running → just report the state
    if session.status == SessionStatus.CREATED:
        raise conflict("Upload at least one photo or audio clip first")

    _verify_media(_media(db, session_id))
    if clear_decisions:
        db.execute(update(MatchResult).where(col(MatchResult.session_id) == session.id).values(teacher_decision=None))
    previous_status = session.status
    set_status(session, SessionStatus.PROCESSING)
    session.error = None
    session.processing_started_at = utcnow()
    session.job_id = match_job_id(str(session.id))
    session.config_snapshot = _config_snapshot(db)  # thresholds actually used for this run
    db.add(session)
    db.commit()

    try:
        enqueue_match(str(session.id))
    except AppError:
        # Queue is down: put the status back so the teacher can retry later.
        session.status = previous_status
        db.add(session)
        db.commit()
        raise
    db.refresh(session)
    return session, True


def session_detail(db: Session, session: AttendanceSession) -> dict:
    """Everything the review screen needs. Embeddings are never included."""
    media = _media(db, session.id)
    rows = db.exec(
        select(MatchResult, User)
        .join(User, col(User.id) == MatchResult.student_id)
        .where(MatchResult.session_id == session.id)
        .order_by(User.roll_no)
    ).all()
    records = {
        r.student_id: r
        for r in db.exec(select(AttendanceRecord).where(AttendanceRecord.session_id == session.id)).all()
    }
    unmatched = db.exec(select(UnmatchedFace).where(UnmatchedFace.session_id == session.id)).all()
    requested_now = open_request_ids(db, [user.id for _, user in rows])

    results = []
    summary = {"present": 0, "uncertain": 0, "not_detected": 0, "unmatched_faces": len(unmatched), "needs_review": 0}
    for result, user in rows:
        summary[result.decision.lower()] += 1
        if needs_teacher_decision(result) and result.teacher_decision is None:
            summary["needs_review"] += 1
        record = records.get(user.id)
        results.append(
            {
                "student_id": user.id,
                "roll_no": user.roll_no,
                "name": user.full_name,
                "decision": result.decision,
                "teacher_decision": result.teacher_decision,
                "face_distance": result.face_distance,
                "voice_score": result.voice_score,
                "fused_score": result.fused_score,
                "crop_url": signed_media_url(result.crop_key),
                "has_biometrics": result.has_biometrics,
                "face_update_pending": result.face_update_pending,
                "face_update_requested": user.id in requested_now,
                "final_status": record.status if record else None,
                "final_source": record.source if record else None,
            }
        )

    return {
        "id": session.id,
        "class_id": session.class_id,
        "session_date": session.session_date,
        "period": session.period,
        "status": session.status,
        "error": session.error,
        "photo_count": sum(1 for m in media if m.kind == "PHOTO"),
        "audio_count": sum(1 for m in media if m.kind == "AUDIO"),
        # Uploaded files, so the teacher can see and remove them before saving.
        "media": [
            {
                "id": m.id,
                "kind": m.kind,
                "url": signed_media_url(m.object_key) if m.kind == "PHOTO" else None,
                "created_at": m.created_at,
            }
            for m in sorted(media, key=lambda item: item.created_at)
            if m.deleted_at is None
        ],
        "processing_ms": session.processing_ms,
        "summary": summary,
        "results": results,
        "unmatched_faces": [
            {"id": f.id, "crop_url": signed_media_url(f.crop_key), "best_distance": f.best_distance} for f in unmatched
        ],
    }


def needs_teacher_decision(result: MatchResult) -> bool:
    """UNCERTAIN results and students without biometrics must be decided by the teacher."""
    return result.decision == "UNCERTAIN" or not result.has_biometrics


def set_teacher_decision(
    db: Session, teacher: User, session_id: uuid.UUID, student_id: uuid.UUID, decision: str | None
) -> None:
    session = get_owned_session(db, session_id, teacher, for_update=True)
    if session.status != SessionStatus.REVIEW:
        raise conflict("Decisions can only be changed during review (use a correction after finalizing)")
    result = db.get(MatchResult, (session.id, student_id))
    if result is None:
        raise not_found("Student result")
    result.teacher_decision = decision
    db.add(result)
    db.commit()


def _final_status_and_source(result: MatchResult) -> tuple[str, str]:
    ai_status = "PRESENT" if result.decision == "PRESENT" else "ABSENT"
    if not result.has_biometrics:
        return result.teacher_decision or "ABSENT", "MANUAL"
    if result.teacher_decision is None:
        return ai_status, "AI_CONFIRMED"
    if result.decision == "UNCERTAIN" or result.teacher_decision != ai_status:
        return result.teacher_decision, "TEACHER_OVERRIDE"
    return result.teacher_decision, "AI_CONFIRMED"


def finalize(db: Session, teacher: User, session_id: uuid.UUID) -> None:
    """Write attendance records + audit entry + status FINALIZED in ONE transaction."""
    session = get_owned_session(db, session_id, teacher, for_update=True)
    results = list(db.exec(select(MatchResult).where(MatchResult.session_id == session.id)).all())

    unresolved = [r for r in results if needs_teacher_decision(r) and r.teacher_decision is None]
    if unresolved:
        raise conflict(f"Please decide for {len(unresolved)} student(s) marked for review first", "REVIEW_INCOMPLETE")
    set_status(session, SessionStatus.FINALIZED)

    counts = {"PRESENT": 0, "ABSENT": 0}
    for result in results:
        status, source = _final_status_and_source(result)
        counts[status] += 1
        db.add(AttendanceRecord(session_id=session.id, student_id=result.student_id, status=status, source=source))

    session.finalized_at = utcnow()
    db.add(session)
    add_audit(db, teacher.id, "SESSION_FINALIZE", "session", session.id, after=counts)
    db.commit()


def correct_attendance(
    db: Session, teacher: User, session_id: uuid.UUID, student_id: uuid.UUID, status: str, reason: str
) -> None:
    """FR-A12: change a finalized record. A reason is required and an audit entry is written."""
    session = get_owned_session(db, session_id, teacher, for_update=True)
    if session.status != SessionStatus.FINALIZED:
        raise conflict("Corrections are only possible after finalizing")
    record = db.get(AttendanceRecord, (session.id, student_id))
    if record is None:
        raise not_found("Attendance record")

    before = {"status": record.status, "source": record.source}
    record.status = status
    record.source = "TEACHER_OVERRIDE"
    record.updated_at = utcnow()
    db.add(record)
    add_audit(
        db,
        teacher.id,
        "ATTENDANCE_CORRECT",
        "attendance_record",
        f"{session.id}:{student_id}",
        before=before,
        after={"status": record.status, "source": record.source},
        reason=reason.strip(),
    )
    db.commit()
