import uuid

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from snapclass.api.deps import DbSession, Teacher
from snapclass.core.config import settings
from snapclass.core.uploads import image_extension, read_upload
from snapclass.schemas import AttendanceCorrection, ResultUpdate, SessionDetail
from snapclass.services import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: uuid.UUID, teacher: Teacher, db: DbSession) -> dict:
    session = session_service.get_owned_session(db, session_id, teacher)
    return session_service.session_detail(db, session)


@router.post("/{session_id}/media", response_model=SessionDetail)
async def upload_media(
    session_id: uuid.UUID,
    teacher: Teacher,
    db: DbSession,
    photos: list[UploadFile] = File(default=[]),
    audio: UploadFile | None = File(default=None),
) -> dict:
    """Upload 1–4 class photos and/or one audio clip (≤ 60 s is used)."""
    photo_files = []
    for photo in photos[: session_service.MAX_PHOTOS + 1]:
        data = await read_upload(photo, "image", settings.max_photo_mb)
        photo_files.append((data, image_extension(data)))
    audio_data = await read_upload(audio, "audio", settings.max_audio_mb) if audio else None

    session_service.add_media(db, teacher, session_id, photo_files, audio_data)
    return session_service.session_detail(db, session_service.get_owned_session(db, session_id, teacher))


@router.delete("/{session_id}/media/{media_id}", response_model=SessionDetail)
def remove_media(session_id: uuid.UUID, media_id: uuid.UUID, teacher: Teacher, db: DbSession) -> dict:
    """Remove one uploaded photo or the audio clip (before attendance is saved)."""
    session_service.remove_media(db, teacher, session_id, media_id)
    return session_service.session_detail(db, session_service.get_owned_session(db, session_id, teacher))


@router.post("/{session_id}/process", response_model=SessionDetail)
def process(session_id: uuid.UUID, teacher: Teacher, db: DbSession, clear_decisions: bool = False) -> JSONResponse:
    """Queue the match job. 202 when queued now, 200 when it was already queued/done (idempotent).

    When checking again after adding photos, the teacher's choices are kept unless clear_decisions=true.
    """
    session, queued_now = session_service.start_processing(db, teacher, session_id, clear_decisions)
    detail = SessionDetail.model_validate(session_service.session_detail(db, session))
    return JSONResponse(status_code=202 if queued_now else 200, content=detail.model_dump(mode="json"))


@router.patch("/{session_id}/results/{student_id}", status_code=204)
def set_decision(
    session_id: uuid.UUID, student_id: uuid.UUID, body: ResultUpdate, teacher: Teacher, db: DbSession
) -> None:
    session_service.set_teacher_decision(db, teacher, session_id, student_id, body.teacher_decision)


@router.post("/{session_id}/finalize", response_model=SessionDetail)
def finalize(session_id: uuid.UUID, teacher: Teacher, db: DbSession) -> dict:
    session_service.finalize(db, teacher, session_id)
    return session_service.session_detail(db, session_service.get_owned_session(db, session_id, teacher))


@router.patch("/{session_id}/attendance/{student_id}", status_code=204)
def correct(
    session_id: uuid.UUID, student_id: uuid.UUID, body: AttendanceCorrection, teacher: Teacher, db: DbSession
) -> None:
    session_service.correct_attendance(db, teacher, session_id, student_id, body.status, body.reason)
