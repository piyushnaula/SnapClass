"""Face photo update requests: "please upload a new face photo".

Flow:
1. A teacher sees that a student is not recognised (old selfie, new glasses, ...)
   and asks for new face photos.
2. While the request is open, the match job skips this student, so they are
   never marked present automatically (the teacher can still mark them by hand).
3. The student sees the request when they sign in and uploads new photos.
4. When the new photos are accepted, every open request for them is closed.
"""

import uuid

from sqlmodel import Session, col, select

from snapclass.core.errors import AppError
from snapclass.models import Classroom, Enrollment, FaceUpdateRequest, User, utcnow
from snapclass.services.audit import add_audit
from snapclass.services.class_service import get_owned_class

# For example: the student was removed from the class after the photos were checked.
NOT_IN_CLASS = AppError(404, "NOT_FOUND", "This student is no longer in this class.")


def _open_requests_query(student_id: uuid.UUID):  # noqa: ANN202
    return select(FaceUpdateRequest).where(
        FaceUpdateRequest.student_id == student_id, col(FaceUpdateRequest.resolved_at).is_(None)
    )


def open_request_ids(db: Session, student_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Which of these students have an open request right now."""
    if not student_ids:
        return set()
    rows = db.exec(
        select(FaceUpdateRequest.student_id).where(
            col(FaceUpdateRequest.student_id).in_(student_ids), col(FaceUpdateRequest.resolved_at).is_(None)
        )
    ).all()
    return set(rows)


def request_new_photo(
    db: Session, teacher: User, class_id: uuid.UUID, student_id: uuid.UUID, reason: str, session_id: uuid.UUID | None
) -> FaceUpdateRequest:
    """Teacher asks a student of their own class for new face photos. Idempotent."""
    classroom = get_owned_class(db, class_id, teacher)  # 404 if not this teacher's class
    if db.get(Enrollment, (classroom.id, student_id)) is None:
        raise NOT_IN_CLASS

    existing = db.exec(_open_requests_query(student_id)).first()
    if existing is not None:
        return existing  # one open request is enough

    request = FaceUpdateRequest(
        student_id=student_id,
        requested_by=teacher.id,
        class_id=classroom.id,
        session_id=session_id,
        reason=reason.strip(),
    )
    db.add(request)
    add_audit(db, teacher.id, "FACE_UPDATE_REQUESTED", "user", student_id, after={"reason": request.reason})
    db.commit()
    db.refresh(request)
    return request


def cancel_requests(db: Session, teacher: User, class_id: uuid.UUID, student_id: uuid.UUID) -> None:
    """Teacher withdraws the request (for example, pressed the button by mistake)."""
    classroom = get_owned_class(db, class_id, teacher)
    if db.get(Enrollment, (classroom.id, student_id)) is None:
        raise NOT_IN_CLASS
    for request in db.exec(_open_requests_query(student_id)).all():
        request.resolved_at = utcnow()
        db.add(request)
    add_audit(db, teacher.id, "FACE_UPDATE_CANCELLED", "user", student_id)
    db.commit()


def resolve_for_student(db: Session, student_id: uuid.UUID) -> int:
    """Close every open request (new face photos were accepted). The caller commits."""
    requests = db.exec(_open_requests_query(student_id)).all()
    for request in requests:
        request.resolved_at = utcnow()
        db.add(request)
    return len(requests)


def open_request_for_student(db: Session, student: User) -> dict | None:
    """What the student sees: the newest open request, in plain words."""
    row = db.exec(
        select(FaceUpdateRequest, User, Classroom)
        .join(User, col(User.id) == FaceUpdateRequest.requested_by)
        .join(Classroom, col(Classroom.id) == FaceUpdateRequest.class_id)
        .where(FaceUpdateRequest.student_id == student.id, col(FaceUpdateRequest.resolved_at).is_(None))
        .order_by(col(FaceUpdateRequest.created_at).desc())
    ).first()
    if row is None:
        return None
    request, teacher, classroom = row
    return {
        "reason": request.reason,
        "requested_by": teacher.full_name,
        "subject": classroom.subject,
        "created_at": request.created_at,
    }
