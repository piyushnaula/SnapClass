import uuid
from datetime import date

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from snapclass.api.deps import DbSession, Teacher
from snapclass.schemas import (
    ClassCreate,
    ClassOut,
    FaceUpdateRequestIn,
    JoinCodeCreate,
    JoinCodeOut,
    ReportOut,
    RosterStudent,
    SessionCreate,
    SessionListItem,
)
from snapclass.services import class_service, face_update_service, report_service, session_service

router = APIRouter(prefix="/classes", tags=["classes"])


def _class_out(db: DbSession, classroom) -> dict:  # noqa: ANN001
    return {**classroom.model_dump(), "student_count": class_service.student_count(db, classroom.id)}


@router.post("", response_model=ClassOut, status_code=201)
def create_class(body: ClassCreate, teacher: Teacher, db: DbSession) -> dict:
    return _class_out(db, class_service.create_class(db, teacher, body))


@router.get("", response_model=list[ClassOut])
def list_classes(teacher: Teacher, db: DbSession) -> list[dict]:
    return [_class_out(db, c) for c in class_service.list_classes(db, teacher)]


@router.get("/{class_id}", response_model=ClassOut)
def get_class(class_id: uuid.UUID, teacher: Teacher, db: DbSession) -> dict:
    return _class_out(db, class_service.get_owned_class(db, class_id, teacher))


@router.post("/{class_id}/join-codes", response_model=JoinCodeOut, status_code=201)
def create_join_code(class_id: uuid.UUID, body: JoinCodeCreate, teacher: Teacher, db: DbSession) -> dict:
    classroom = class_service.get_owned_class(db, class_id, teacher)
    return class_service.create_join_code(db, classroom, body.hours, body.max_uses)


@router.get("/{class_id}/students", response_model=list[RosterStudent])
def list_students(class_id: uuid.UUID, teacher: Teacher, db: DbSession) -> list[dict]:
    return class_service.roster(db, class_service.get_owned_class(db, class_id, teacher))


@router.delete("/{class_id}/students/{student_id}", status_code=204)
def remove_student(class_id: uuid.UUID, student_id: uuid.UUID, teacher: Teacher, db: DbSession) -> None:
    classroom = class_service.get_owned_class(db, class_id, teacher)
    class_service.remove_student(db, teacher, classroom, student_id)


@router.post("/{class_id}/students/{student_id}/face-update-request", status_code=201)
def request_face_update(
    class_id: uuid.UUID, student_id: uuid.UUID, body: FaceUpdateRequestIn, teacher: Teacher, db: DbSession
) -> dict:
    """Ask a student for new face photos. Until they upload, they are not marked present automatically."""
    request = face_update_service.request_new_photo(db, teacher, class_id, student_id, body.reason, body.session_id)
    return {"id": request.id, "reason": request.reason, "created_at": request.created_at}


@router.delete("/{class_id}/students/{student_id}/face-update-request", status_code=204)
def cancel_face_update(class_id: uuid.UUID, student_id: uuid.UUID, teacher: Teacher, db: DbSession) -> None:
    face_update_service.cancel_requests(db, teacher, class_id, student_id)


@router.get("/{class_id}/sessions", response_model=list[SessionListItem])
def list_sessions(class_id: uuid.UUID, teacher: Teacher, db: DbSession) -> list:
    return session_service.list_sessions(db, class_service.get_owned_class(db, class_id, teacher))


@router.post("/{class_id}/sessions", response_model=SessionListItem, status_code=201)
def create_session(class_id: uuid.UUID, body: SessionCreate, teacher: Teacher, db: DbSession) -> object:
    classroom = class_service.get_owned_class(db, class_id, teacher)
    return session_service.create_session(db, teacher, classroom, body.session_date, body.period)


@router.get("/{class_id}/report", response_model=ReportOut)
def report(
    class_id: uuid.UUID,
    request: Request,
    teacher: Teacher,
    db: DbSession,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    below: bool = False,
    format: str | None = None,
) -> object:
    """Attendance % per student. CSV with `Accept: text/csv` or `?format=csv`."""
    classroom = class_service.get_owned_class(db, class_id, teacher)
    data = report_service.class_report(db, classroom, from_date, to_date, below_only=below)
    if format == "csv" or "text/csv" in request.headers.get("accept", ""):
        filename = f"attendance-{classroom.subject}-{classroom.section}.csv".replace(" ", "_")
        return Response(
            content=report_service.report_to_csv(data),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return data
