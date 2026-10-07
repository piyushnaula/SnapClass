"""Classes, invite codes and the class roster (FR-A3, FR-A4)."""

import base64
import io
import secrets
import uuid
from datetime import timedelta

import qrcode
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from snapclass.core.config import settings
from snapclass.core.errors import AppError, conflict, not_found
from snapclass.models import (
    Classroom,
    Enrollment,
    FaceEmbedding,
    FaceUpdateRequest,
    JoinCode,
    User,
    VoiceEmbedding,
    utcnow,
)
from snapclass.schemas import ClassCreate
from snapclass.services.audit import add_audit


def get_owned_class(db: Session, class_id: uuid.UUID, teacher: User) -> Classroom:
    """Load a class only if this teacher owns it. Otherwise 404 (IDOR protection)."""
    classroom = db.exec(select(Classroom).where(Classroom.id == class_id, Classroom.teacher_id == teacher.id)).first()
    if classroom is None:
        raise not_found("Class")
    return classroom


def student_count(db: Session, class_id: uuid.UUID) -> int:
    return db.exec(select(func.count()).select_from(Enrollment).where(Enrollment.class_id == class_id)).one()


def create_class(db: Session, teacher: User, data: ClassCreate) -> Classroom:
    classroom = Classroom(teacher_id=teacher.id, **data.model_dump())
    db.add(classroom)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("A class with this subject, section and semester already exists") from None
    db.refresh(classroom)
    return classroom


def list_classes(db: Session, teacher: User) -> list[Classroom]:
    return list(
        db.exec(select(Classroom).where(Classroom.teacher_id == teacher.id).order_by(col(Classroom.created_at))).all()
    )


def _qr_png_base64(text: str) -> str:
    image = qrcode.make(text)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def create_join_code(db: Session, classroom: Classroom, hours: int | None, max_uses: int | None) -> dict:
    code = secrets.token_urlsafe(6)  # 6 random bytes → 8 URL-safe characters
    join_code = JoinCode(
        code=code,
        class_id=classroom.id,
        expires_at=utcnow() + timedelta(hours=hours or settings.join_code_hours),
        max_uses=max_uses,
    )
    db.add(join_code)
    db.commit()
    join_url = f"{settings.frontend_url}/#/join/{code}"
    return {
        "code": code,
        "join_url": join_url,
        "qr_png_base64": _qr_png_base64(join_url),
        "expires_at": join_code.expires_at,
        "max_uses": max_uses,
    }


def get_valid_join_code(db: Session, code: str) -> tuple[JoinCode, Classroom]:
    join_code = db.get(JoinCode, code)
    if join_code is None or join_code.expires_at < utcnow():
        raise not_found("Join code")
    if join_code.max_uses is not None and join_code.uses >= join_code.max_uses:
        raise AppError(410, "JOIN_CODE_USED_UP", "This join code has been used up")
    classroom = db.get(Classroom, join_code.class_id)
    if classroom is None:
        raise not_found("Join code")
    return join_code, classroom


def join_class(db: Session, code: str, student: User) -> tuple[Classroom, bool]:
    """Add a signed-in student to the class of this invite code.

    Returns (class, already_joined). Joining twice is harmless.
    """
    join_code, classroom = get_valid_join_code(db, code)
    if db.get(Enrollment, (classroom.id, student.id)) is not None:
        return classroom, True
    db.add(Enrollment(class_id=classroom.id, student_id=student.id))
    join_code.uses += 1
    db.add(join_code)
    db.commit()
    return classroom, False


def roster(db: Session, classroom: Classroom) -> list[dict]:
    """Students in the class with how many face/voice samples they have (never the embeddings)."""
    face_counts = (
        select(FaceEmbedding.student_id, func.count().label("n")).group_by(col(FaceEmbedding.student_id)).subquery()
    )
    voice_counts = (
        select(VoiceEmbedding.student_id, func.count().label("n")).group_by(col(VoiceEmbedding.student_id)).subquery()
    )
    rows = db.exec(
        select(User, face_counts.c.n, voice_counts.c.n)
        .join(Enrollment, col(Enrollment.student_id) == User.id)
        .outerjoin(face_counts, face_counts.c.student_id == User.id)
        .outerjoin(voice_counts, voice_counts.c.student_id == User.id)
        .where(Enrollment.class_id == classroom.id)
        .order_by(User.roll_no)
    ).all()
    # Students with an open "please upload a new face photo" request.
    requested = set(
        db.exec(
            select(FaceUpdateRequest.student_id).where(
                col(FaceUpdateRequest.student_id).in_([user.id for user, _, _ in rows]),
                col(FaceUpdateRequest.resolved_at).is_(None),
            )
        ).all()
    )
    return [
        {
            "id": user.id,
            "roll_no": user.roll_no,
            "full_name": user.full_name,
            "email": user.email,
            "face_samples": faces or 0,
            "voice_samples": voices or 0,
            "face_update_requested": user.id in requested,
        }
        for user, faces, voices in rows
    ]


def remove_student(db: Session, teacher: User, classroom: Classroom, student_id: uuid.UUID) -> None:
    enrollment = db.get(Enrollment, (classroom.id, student_id))
    if enrollment is None:
        raise not_found("Student")
    db.delete(enrollment)
    add_audit(db, teacher.id, "STUDENT_REMOVED", "class", classroom.id, before={"student_id": str(student_id)})
    db.commit()
