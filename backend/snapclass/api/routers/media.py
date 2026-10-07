"""Serve face crops through short-lived signed URLs (works inside <img src>)."""

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from snapclass.core.errors import AppError, not_found
from snapclass.core.security import verify_media_signature
from snapclass.core.storage import storage

router = APIRouter(tags=["media"])


@router.get("/media/{key:path}")
def get_media(key: str, exp: int = Query(...), sig: str = Query(..., max_length=128)) -> FileResponse:
    # Only face crops and class photos are served (never audio or enrollment selfies),
    # and only through a link the server signed for the teacher who owns the lecture.
    is_crop = key.startswith("crops/")
    is_class_photo = key.startswith("sessions/") and key.endswith((".jpg", ".png"))
    if not (is_crop or is_class_photo):
        raise not_found("File")
    if not verify_media_signature(key, exp, sig):
        raise AppError(403, "FORBIDDEN", "Link expired or invalid")
    if not storage.exists(key):
        raise not_found("File")
    return FileResponse(
        storage.local_path(key),
        media_type="image/png" if key.endswith(".png") else "image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )
