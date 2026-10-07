"""Database tables (SQLModel). Mirrors the schema in spec section A.6.

Two important ideas are built into the schema:
* match_results (the AI's proposal) and attendance_records (the truth) are
  separate tables. Only a teacher action writes attendance_records.
* Embeddings are deleted with ON DELETE CASCADE when a student erases their
  biometric data, but their attendance history stays.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

FACE_DIM = 128
VOICE_DIM = 256


def utcnow() -> datetime:
    return datetime.now(UTC)


def created_at_field() -> Any:
    """A NOT NULL 'timestamptz' column that defaults to now (UTC)."""
    return Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


def optional_time_field() -> Any:
    """A nullable 'timestamptz' column."""
    return Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


# ---------- Users & auth ----------


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('ADMIN','TEACHER','STUDENT')", name="ck_users_role"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Teachers and the admin sign in with email. Students sign in with their
    # student ID (roll_no) and may have no email. Both are unique when present.
    email: str | None = Field(default=None, unique=True, index=True)  # stored lower-case
    password_hash: str
    full_name: str
    role: str
    roll_no: str | None = Field(default=None, unique=True)  # student ID, stored upper-case
    is_active: bool = True
    created_at: datetime = created_at_field()


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    token_hash: str = Field(unique=True)
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    revoked_at: datetime | None = optional_time_field()
    replaced_by: uuid.UUID | None = Field(default=None, foreign_key="refresh_tokens.id")
    created_at: datetime = created_at_field()


# ---------- Classes & enrollment ----------


class Classroom(SQLModel, table=True):
    __tablename__ = "classes"
    __table_args__ = (UniqueConstraint("subject", "section", "semester", name="uq_classes_subject_section_sem"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    teacher_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    subject: str
    section: str
    semester: int
    min_attendance_pct: float = 75.0
    created_at: datetime = created_at_field()


class JoinCode(SQLModel, table=True):
    __tablename__ = "join_codes"

    code: str = Field(primary_key=True)  # 8-char random, URL-safe
    class_id: uuid.UUID = Field(foreign_key="classes.id", ondelete="CASCADE")
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    max_uses: int | None = None
    uses: int = 0
    created_at: datetime = created_at_field()


class Enrollment(SQLModel, table=True):
    __tablename__ = "enrollments"

    class_id: uuid.UUID = Field(foreign_key="classes.id", primary_key=True, ondelete="CASCADE")
    student_id: uuid.UUID = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    enrolled_at: datetime = created_at_field()


# ---------- Consent & biometrics ----------


class ConsentText(SQLModel, table=True):
    __tablename__ = "consent_texts"

    version: int = Field(primary_key=True, sa_column_kwargs={"autoincrement": False})
    body: str
    published_at: datetime = created_at_field()


class Consent(SQLModel, table=True):
    __tablename__ = "consents"

    student_id: uuid.UUID = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    version: int = Field(foreign_key="consent_texts.version", primary_key=True)
    granted_at: datetime = created_at_field()
    withdrawn_at: datetime | None = optional_time_field()


class FaceEmbedding(SQLModel, table=True):
    __tablename__ = "face_embeddings"
    __table_args__ = (
        # HNSW index for "find the nearest face among ALL students" (duplicate check).
        Index(
            "face_emb_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_l2_ops"},
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    student_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    embedding: Any = Field(sa_column=Column(Vector(FACE_DIM), nullable=False))
    quality: float  # 0..1 composite of detector confidence and sharpness
    model_ver: str
    created_at: datetime = created_at_field()


class VoiceEmbedding(SQLModel, table=True):
    __tablename__ = "voice_embeddings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    student_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    embedding: Any = Field(sa_column=Column(Vector(VOICE_DIM), nullable=False))
    model_ver: str
    created_at: datetime = created_at_field()


class FaceUpdateRequest(SQLModel, table=True):
    """A teacher asked a student for new face photos (e.g. the old selfie no longer matches).

    While a request is open, the student is NOT marked present automatically in any
    lecture. It closes by itself when new face photos are accepted.
    """

    __tablename__ = "face_update_requests"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    student_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    requested_by: uuid.UUID = Field(foreign_key="users.id")
    class_id: uuid.UUID = Field(foreign_key="classes.id", ondelete="CASCADE")
    session_id: uuid.UUID | None = Field(default=None, foreign_key="sessions.id", ondelete="SET NULL")
    reason: str
    created_at: datetime = created_at_field()
    resolved_at: datetime | None = optional_time_field()  # set when new photos are accepted or the teacher cancels


class BiometricJob(SQLModel, table=True):
    """Tracks one enrollment upload so the student can see the result."""

    __tablename__ = "biometric_jobs"
    __table_args__ = (
        CheckConstraint("kind IN ('FACE','VOICE')", name="ck_biometric_jobs_kind"),
        CheckConstraint("status IN ('QUEUED','DONE','FAILED')", name="ck_biometric_jobs_status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    student_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    kind: str
    status: str = "QUEUED"
    message: str | None = None
    created_at: datetime = created_at_field()
    finished_at: datetime | None = optional_time_field()


# ---------- Sessions & matching ----------


class AttendanceSession(SQLModel, table=True):
    """One lecture (class + date + period). Called 'sessions' in the spec."""

    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("class_id", "session_date", "period", name="uq_sessions_class_date_period"),
        CheckConstraint(
            "status IN ('CREATED','UPLOADED','PROCESSING','REVIEW','FINALIZED','FAILED')",
            name="ck_sessions_status",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    class_id: uuid.UUID = Field(foreign_key="classes.id", index=True)
    teacher_id: uuid.UUID = Field(foreign_key="users.id")
    session_date: date
    period: int
    status: str = Field(default="CREATED", index=True)
    error: str | None = None
    job_id: str | None = None
    # The thresholds and model versions used, so every decision can be explained later.
    config_snapshot: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    processing_started_at: datetime | None = optional_time_field()
    processing_ms: int | None = None  # how long the match job took
    created_at: datetime = created_at_field()
    finalized_at: datetime | None = optional_time_field()


class SessionMedia(SQLModel, table=True):
    __tablename__ = "session_media"
    __table_args__ = (CheckConstraint("kind IN ('PHOTO','AUDIO')", name="ck_session_media_kind"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="sessions.id", ondelete="CASCADE", index=True)
    kind: str
    object_key: str
    sha256: str
    size_bytes: int
    created_at: datetime = created_at_field()
    deleted_at: datetime | None = optional_time_field()  # set by the retention job


class MatchResult(SQLModel, table=True):
    """The AI's proposal for one student in one session."""

    __tablename__ = "match_results"
    __table_args__ = (
        CheckConstraint("decision IN ('PRESENT','UNCERTAIN','NOT_DETECTED')", name="ck_match_results_decision"),
        CheckConstraint(
            "teacher_decision IS NULL OR teacher_decision IN ('PRESENT','ABSENT')",
            name="ck_match_results_teacher_decision",
        ),
    )

    session_id: uuid.UUID = Field(foreign_key="sessions.id", primary_key=True, ondelete="CASCADE")
    student_id: uuid.UUID = Field(foreign_key="users.id", primary_key=True)
    decision: str
    face_distance: float | None = None  # best L2 distance, None if no face matched
    voice_score: float | None = None  # best cosine similarity, None if no voice matched
    fused_score: float | None = None
    crop_key: str | None = None  # face crop shown on the review screen
    has_biometrics: bool = True  # False → student erased data, mark manually
    face_update_pending: bool = False  # True → skipped because a new face photo was requested
    teacher_decision: str | None = None  # set when the teacher toggles during review


class UnmatchedFace(SQLModel, table=True):
    """A face in a class photo that matched nobody on the roster (visitor, unenrolled)."""

    __tablename__ = "unmatched_faces"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="sessions.id", ondelete="CASCADE", index=True)
    crop_key: str
    best_distance: float | None = None


# ---------- Attendance (system of record) ----------


class AttendanceRecord(SQLModel, table=True):
    __tablename__ = "attendance_records"
    __table_args__ = (
        CheckConstraint("status IN ('PRESENT','ABSENT')", name="ck_attendance_status"),
        CheckConstraint("source IN ('AI_CONFIRMED','TEACHER_OVERRIDE','MANUAL')", name="ck_attendance_source"),
    )

    session_id: uuid.UUID = Field(foreign_key="sessions.id", primary_key=True)
    student_id: uuid.UUID = Field(foreign_key="users.id", primary_key=True, index=True)
    status: str
    source: str
    updated_at: datetime = created_at_field()


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    actor_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    action: str = Field(index=True)  # e.g. SESSION_FINALIZE, ATTENDANCE_CORRECT
    entity_type: str
    entity_id: str
    before: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    after: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    reason: str | None = None
    at: datetime = created_at_field()


class AppSetting(SQLModel, table=True):
    """Small key/value table for settings the admin can change at runtime."""

    __tablename__ = "app_settings"

    key: str = Field(primary_key=True)
    value: dict = Field(sa_column=Column(JSONB, nullable=False))
    updated_at: datetime = created_at_field()
