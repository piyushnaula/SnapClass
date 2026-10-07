"""Request and response models for the HTTP API (validated by Pydantic).

These are separate from the database tables on purpose: the API decides
exactly which fields leave the server (for example, never embeddings or
password hashes).
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Role = Literal["ADMIN", "TEACHER", "STUDENT"]


# ---------- Auth ----------


def clean_student_id(value: str) -> str:
    """Student IDs are stored upper-case, e.g. ' 23cse041 ' -> '23CSE041'."""
    value = value.strip().upper()
    if not 3 <= len(value) <= 20 or not value.replace("-", "").isalnum():
        raise ValueError("student ID must be 3-20 letters, digits or '-'")
    return value


class LoginRequest(BaseModel):
    # Students sign in with their student ID; teachers and the admin with their email.
    login_id: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    """A student creates their own account with their college student ID."""

    student_id: str
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("student_id")
    @classmethod
    def check_student_id(cls, value: str) -> str:
        return clean_student_id(value)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.split())


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=200)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str | None = None  # students may have no email
    full_name: str
    role: Role
    roll_no: str | None = None
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 (not a password)
    user: UserOut


# ---------- Admin ----------


class TeacherCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class UserStatusUpdate(BaseModel):
    is_active: bool


class SettingsUpdate(BaseModel):
    thresholds: dict[str, float] | None = None
    retention_days: int | None = Field(default=None, ge=1, le=90)
    blur_threshold: float | None = Field(default=None, ge=0, le=1000)


# ---------- Classes ----------


class ClassCreate(BaseModel):
    subject: str = Field(min_length=2, max_length=100)
    section: str = Field(min_length=1, max_length=20)
    semester: int = Field(ge=1, le=12)
    min_attendance_pct: float = Field(default=75.0, ge=0, le=100)


class ClassOut(BaseModel):
    id: uuid.UUID
    subject: str
    section: str
    semester: int
    min_attendance_pct: float
    student_count: int = 0


class JoinCodeCreate(BaseModel):
    hours: int | None = Field(default=None, ge=1, le=24 * 30)
    max_uses: int | None = Field(default=None, ge=1, le=1000)


class JoinCodeOut(BaseModel):
    code: str
    join_url: str
    qr_png_base64: str
    expires_at: datetime
    max_uses: int | None


class RosterStudent(BaseModel):
    id: uuid.UUID
    roll_no: str | None
    full_name: str
    email: str | None
    face_samples: int
    voice_samples: int
    face_update_requested: bool  # teacher asked for a new face photo and it is not done yet


# ---------- Join a class (signed-in student) ----------


class JoinInfo(BaseModel):
    subject: str
    section: str
    semester: int


class JoinResult(BaseModel):
    class_id: uuid.UUID
    subject: str
    already_joined: bool


# ---------- Face photo update requests ----------


class FaceUpdateRequestIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
    session_id: uuid.UUID | None = None  # the lecture where the student was not recognised


class FaceUpdateRequestOut(BaseModel):
    reason: str
    requested_by: str  # teacher's name
    subject: str
    created_at: datetime


# ---------- Consent & biometrics ----------


class ConsentOut(BaseModel):
    version: int
    body: str
    accepted: bool


class ConsentAccept(BaseModel):
    version: int


class BiometricJobOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    message: str | None
    created_at: datetime


class BiometricStatus(BaseModel):
    consent_version: int | None
    consent_current: bool
    face_samples: int
    voice_samples: int
    jobs: list[BiometricJobOut]
    voice_sentence: str
    face_update_request: FaceUpdateRequestOut | None = None


# ---------- Sessions ----------


class SessionCreate(BaseModel):
    session_date: date
    period: int = Field(ge=1, le=12)


class SessionListItem(BaseModel):
    id: uuid.UUID
    session_date: date
    period: int
    status: str
    created_at: datetime


class ResultOut(BaseModel):
    student_id: uuid.UUID
    roll_no: str | None
    name: str
    decision: str
    teacher_decision: str | None
    face_distance: float | None
    voice_score: float | None
    fused_score: float | None
    crop_url: str | None
    has_biometrics: bool
    face_update_pending: bool = False  # excluded from automatic matching in THIS lecture
    face_update_requested: bool = False  # a request is open right now
    final_status: str | None = None  # attendance record, after finalize
    final_source: str | None = None


class UnmatchedFaceOut(BaseModel):
    id: uuid.UUID
    crop_url: str | None
    best_distance: float | None


class MediaOut(BaseModel):
    id: uuid.UUID
    kind: str  # PHOTO or AUDIO
    url: str | None  # signed link for photos, None for audio
    created_at: datetime


class SessionDetail(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    session_date: date
    period: int
    status: str
    error: str | None
    photo_count: int
    audio_count: int
    media: list[MediaOut]
    processing_ms: int | None
    summary: dict[str, int]
    results: list[ResultOut]
    unmatched_faces: list[UnmatchedFaceOut]


class ResultUpdate(BaseModel):
    teacher_decision: Literal["PRESENT", "ABSENT"] | None


class AttendanceCorrection(BaseModel):
    status: Literal["PRESENT", "ABSENT"]
    reason: str = Field(min_length=3, max_length=500)


# ---------- Reports ----------


class ReportRow(BaseModel):
    student_id: uuid.UUID
    roll_no: str | None
    full_name: str
    present: int
    total: int
    pct: float | None
    below_threshold: bool


class ReportOut(BaseModel):
    class_id: uuid.UUID
    from_date: date | None
    to_date: date | None
    min_attendance_pct: float
    rows: list[ReportRow]


class MyClassAttendance(BaseModel):
    class_id: uuid.UUID
    subject: str
    section: str
    semester: int
    present: int
    total: int
    pct: float | None
    min_attendance_pct: float
    history: list[dict]  # every lecture, newest first
