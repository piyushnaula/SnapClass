"""Student self-service: consent, biometric enrollment, own attendance (FR-A4 to FR-A7, FR-A14)."""

from fastapi import APIRouter, File, UploadFile

from snapclass.api.deps import DbSession, Student
from snapclass.core.config import settings
from snapclass.core.uploads import image_extension, read_upload
from snapclass.schemas import BiometricJobOut, BiometricStatus, ConsentAccept, ConsentOut, MyClassAttendance
from snapclass.services import biometric_service, report_service

router = APIRouter(tags=["student"])


@router.get("/consent/current", response_model=ConsentOut)
def current_consent(student: Student, db: DbSession) -> dict:
    text = biometric_service.current_consent_text(db)
    return {"version": text.version, "body": text.body, "accepted": biometric_service.has_current_consent(db, student)}


@router.post("/consent", status_code=204)
def accept_consent(body: ConsentAccept, student: Student, db: DbSession) -> None:
    biometric_service.accept_consent(db, student, body.version)


@router.get("/me/biometrics", response_model=BiometricStatus)
def biometric_status(student: Student, db: DbSession) -> dict:
    return biometric_service.status(db, student)


@router.post("/me/biometrics/face", response_model=BiometricJobOut, status_code=202)
async def enroll_face(student: Student, db: DbSession, photos: list[UploadFile] = File(...)) -> object:
    files = []
    for photo in photos[:10]:  # hard cap before reading anything big
        data = await read_upload(photo, "image", settings.max_photo_mb)
        files.append((data, image_extension(data)))
    return biometric_service.start_enrollment(db, student, "FACE", files)


@router.post("/me/biometrics/voice", response_model=BiometricJobOut, status_code=202)
async def enroll_voice(student: Student, db: DbSession, clips: list[UploadFile] = File(...)) -> object:
    files = []
    for clip in clips[:10]:
        files.append((await read_upload(clip, "audio", settings.max_audio_mb), "audio"))
    return biometric_service.start_enrollment(db, student, "VOICE", files)


@router.delete("/me/biometrics", status_code=204)
def erase_biometrics(student: Student, db: DbSession) -> None:
    biometric_service.erase_biometrics(db, student)


@router.get("/me/attendance", response_model=list[MyClassAttendance])
def my_attendance(student: Student, db: DbSession) -> list[dict]:
    return report_service.my_attendance(db, student)
