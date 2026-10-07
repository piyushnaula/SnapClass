"""Joining a class with the teacher's invite link or QR code."""

from fastapi import APIRouter, Path

from snapclass.api.deps import DbSession, Student
from snapclass.schemas import JoinInfo, JoinResult
from snapclass.services import class_service

router = APIRouter(prefix="/join", tags=["join"])

CodePath = Path(min_length=4, max_length=16, pattern=r"^[A-Za-z0-9_-]+$")


@router.get("/{code}", response_model=JoinInfo)
def join_info(db: DbSession, code: str = CodePath) -> object:
    """Public: which class this invite is for (shown before signing in)."""
    _, classroom = class_service.get_valid_join_code(db, code)
    return classroom


@router.post("/{code}", response_model=JoinResult)
def join(student: Student, db: DbSession, code: str = CodePath) -> dict:
    """A signed-in student joins the class. Only students can join."""
    classroom, already_joined = class_service.join_class(db, code, student)
    return {"class_id": classroom.id, "subject": classroom.subject, "already_joined": already_joined}
