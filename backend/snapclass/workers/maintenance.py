"""Maintenance tasks run by the scheduler.

* sweep_stuck_sessions  – re-queue sessions stuck in PROCESSING (worker crashed)
* apply_retention       – FR-A16: delete raw session media N days after finalize
* send_weekly_reports   – FR-A18: email each teacher their below-threshold students
"""

import logging
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from sqlmodel import Session, col, select

from snapclass.core.config import settings
from snapclass.core.db import engine
from snapclass.core.storage import storage
from snapclass.models import AttendanceSession, MatchResult, SessionMedia, UnmatchedFace, User, utcnow
from snapclass.services.report_service import below_threshold_by_teacher
from snapclass.services.settings_service import get_setting
from snapclass.workers.queue import enqueue_match, is_job_active, match_job_id

logger = logging.getLogger(__name__)


def sweep_stuck_sessions() -> int:
    """Sessions in PROCESSING for too long with no live job get queued again."""
    cutoff = utcnow() - timedelta(minutes=settings.stuck_session_minutes)
    requeued = 0
    with Session(engine) as db:
        stuck = db.exec(
            select(AttendanceSession).where(
                AttendanceSession.status == "PROCESSING",
                col(AttendanceSession.processing_started_at) < cutoff,
            )
        ).all()
        for session in stuck:
            if is_job_active(match_job_id(str(session.id))):
                continue  # still waiting for a retry or still running
            enqueue_match(str(session.id))
            session.processing_started_at = utcnow()
            db.add(session)
            requeued += 1
        db.commit()
    if requeued:
        logger.warning("Re-queued stuck sessions", extra={"fields": {"count": requeued}})
    return requeued


def apply_retention() -> int:
    """Delete photos, audio and face crops of sessions finalized more than N days ago."""
    with Session(engine) as db:
        days = int(get_setting(db, "retention")["days"])
        cutoff = utcnow() - timedelta(days=days)
        old_sessions = db.exec(
            select(AttendanceSession.id).where(
                AttendanceSession.status == "FINALIZED",
                col(AttendanceSession.finalized_at) < cutoff,
            )
        ).all()
        if not old_sessions:
            return 0

        deleted = 0
        media = db.exec(
            select(SessionMedia).where(
                col(SessionMedia.session_id).in_(old_sessions),
                col(SessionMedia.deleted_at).is_(None),
            )
        ).all()
        for item in media:
            storage.delete(item.object_key)
            item.deleted_at = utcnow()
            db.add(item)
            deleted += 1

        # Face crops are biometric too, so they go as well.
        results = db.exec(
            select(MatchResult).where(
                col(MatchResult.session_id).in_(old_sessions), col(MatchResult.crop_key).is_not(None)
            )
        ).all()
        for result in results:
            if result.crop_key:
                storage.delete(result.crop_key)
            result.crop_key = None
            db.add(result)
        for face in db.exec(select(UnmatchedFace).where(col(UnmatchedFace.session_id).in_(old_sessions))).all():
            storage.delete(face.crop_key)
            db.delete(face)
        db.commit()
    if deleted:
        logger.info("Retention cleanup", extra={"fields": {"deleted_media": deleted}})
    return deleted


def _send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        logger.info(
            "Weekly email (SMTP not configured, logging only)", extra={"fields": {"to": to, "subject": subject}}
        )
        return
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = settings.smtp_from, to, subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


def send_weekly_reports() -> int:
    sent = 0
    with Session(engine) as db:
        teachers = db.exec(select(User).where(User.role == "TEACHER", col(User.is_active).is_(True))).all()
        for teacher in teachers:
            classes = below_threshold_by_teacher(db, teacher.id)
            if not classes:
                continue
            lines = [f"Hello {teacher.full_name},", "", "Students below the attendance threshold:", ""]
            for item in classes:
                lines.append(item["class"])
                for row in item["rows"]:
                    lines.append(f"  {row['roll_no']}  {row['full_name']}  {row['pct']}%")
                lines.append("")
            _send_email(teacher.email, "SnapClass weekly attendance report", "\n".join(lines))
            sent += 1
    return sent
