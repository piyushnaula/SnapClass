"""Admin: manage teachers and see an operational summary (FR-A2, FR-A17)."""

import uuid
from datetime import timedelta

from redis.exceptions import RedisError
from sqlalchemy import func
from sqlmodel import Session, col, select

from snapclass.core.errors import AppError, conflict, not_found
from snapclass.core.security import hash_password
from snapclass.models import AttendanceSession, AuditLog, BiometricJob, Classroom, User, utcnow
from snapclass.schemas import TeacherCreate
from snapclass.services.audit import add_audit
from snapclass.services.auth_service import revoke_all_for_user
from snapclass.workers.queue import queue_depths


def create_teacher(db: Session, admin: User, data: TeacherCreate) -> User:
    email = data.email.lower()
    if db.exec(select(User).where(User.email == email)).first():
        raise conflict("A user with this email already exists")
    teacher = User(email=email, password_hash=hash_password(data.password), full_name=data.full_name, role="TEACHER")
    db.add(teacher)
    db.flush()
    add_audit(db, admin.id, "ROLE_CHANGE", "user", teacher.id, after={"role": "TEACHER", "email": email})
    db.commit()
    db.refresh(teacher)
    return teacher


def list_teachers(db: Session) -> list[User]:
    return list(db.exec(select(User).where(User.role == "TEACHER").order_by(User.full_name)).all())


def set_user_active(db: Session, admin: User, user_id: uuid.UUID, is_active: bool) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User")
    if user.id == admin.id:
        raise AppError(400, "BAD_REQUEST", "You cannot deactivate yourself")
    before = {"is_active": user.is_active}
    user.is_active = is_active
    db.add(user)
    if not is_active:
        revoke_all_for_user(db, user.id)  # log them out everywhere
    add_audit(db, admin.id, "USER_STATUS_CHANGE", "user", user.id, before=before, after={"is_active": is_active})
    db.commit()
    db.refresh(user)
    return user


def _count(db: Session, query) -> int:  # noqa: ANN001
    return int(db.exec(query).one())


def metrics(db: Session) -> dict:
    now = utcnow()
    day_ago = now - timedelta(days=1)

    sessions_by_status = dict(
        db.exec(select(AttendanceSession.status, func.count()).group_by(AttendanceSession.status)).all()
    )
    # p50 / p95 of match-job duration over the last 7 days, computed in Postgres.
    p50, p95 = db.exec(
        select(
            func.percentile_cont(0.5).within_group(col(AttendanceSession.processing_ms)),
            func.percentile_cont(0.95).within_group(col(AttendanceSession.processing_ms)),
        ).where(
            col(AttendanceSession.processing_ms).is_not(None), AttendanceSession.created_at >= now - timedelta(days=7)
        )
    ).one()

    try:
        queues: dict[str, int] | None = queue_depths()
    except RedisError:
        queues = None  # dashboard still works when Redis is down

    duplicate_flags = db.exec(
        select(AuditLog)
        .where(AuditLog.action == "DUPLICATE_FACE_SUSPECTED")
        .order_by(col(AuditLog.at).desc())
        .limit(10)
    ).all()

    return {
        "teachers": _count(db, select(func.count()).select_from(User).where(User.role == "TEACHER")),
        "students": _count(db, select(func.count()).select_from(User).where(User.role == "STUDENT")),
        "classes": _count(db, select(func.count()).select_from(Classroom)),
        "sessions_last_24h": _count(
            db, select(func.count()).select_from(AttendanceSession).where(AttendanceSession.created_at >= day_ago)
        ),
        "sessions_by_status": sessions_by_status,
        "failed_sessions_last_24h": _count(
            db,
            select(func.count())
            .select_from(AttendanceSession)
            .where(AttendanceSession.status == "FAILED", AttendanceSession.created_at >= day_ago),
        ),
        "failed_enrollments_last_24h": _count(
            db,
            select(func.count())
            .select_from(BiometricJob)
            .where(BiometricJob.status == "FAILED", BiometricJob.created_at >= day_ago),
        ),
        "match_job_ms": {"p50": p50, "p95": p95},
        "queue_depth": queues,
        "duplicate_face_flags": [{"at": a.at, "student_id": a.entity_id, "details": a.after} for a in duplicate_flags],
    }


def audit_entries(db: Session, limit: int) -> list[AuditLog]:
    return list(db.exec(select(AuditLog).order_by(col(AuditLog.at).desc()).limit(limit)).all())
