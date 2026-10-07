"""The match job with a fake face model, so the test is fast and exact."""

import math
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
from sqlmodel import select

from snapclass.core.storage import storage
from snapclass.domain.decisions import Thresholds
from snapclass.ml.face import DetectedFace
from snapclass.models import (
    AttendanceSession,
    BiometricJob,
    Classroom,
    Consent,
    ConsentText,
    Enrollment,
    FaceEmbedding,
    FaceUpdateRequest,
    MatchResult,
    SessionMedia,
    UnmatchedFace,
    utcnow,
)
from snapclass.workers import callbacks, enroll_job, maintenance, match_job
from tests.conftest import make_user, tiny_jpeg

DIM = 128


def basis(i: int) -> np.ndarray:
    vector = np.zeros(DIM, dtype=np.float32)
    vector[i] = 1.0
    return vector


class FakeEncoder:
    model_version = "fake-v1"

    def __init__(self, embeddings):
        self.embeddings = embeddings

    def encode(self, image, min_face_px=24):
        return [DetectedFace((5, 5, 40, 40), e, 0.9, 100.0) for e in self.embeddings]


def make_processing_session(db, n_students=3, status="PROCESSING"):
    teacher = make_user(db, "TEACHER", "t@x.com")
    classroom = Classroom(teacher_id=teacher.id, subject="OS", section="B", semester=3)
    db.add(classroom)
    db.commit()
    students = [make_user(db, "STUDENT", f"s{i}@x.com", roll_no=f"R{i}") for i in range(n_students)]
    for i, student in enumerate(students):
        db.add(Enrollment(class_id=classroom.id, student_id=student.id))
        db.add(FaceEmbedding(student_id=student.id, embedding=basis(i), quality=1.0, model_ver="fake-v1"))

    session = AttendanceSession(
        class_id=classroom.id,
        teacher_id=teacher.id,
        session_date=date(2026, 10, 7),
        period=1,
        status=status,
        config_snapshot={"thresholds": Thresholds().to_dict()},
        processing_started_at=utcnow(),
    )
    db.add(session)
    db.commit()
    key = f"sessions/{session.id}/photo.jpg"
    storage.save(key, tiny_jpeg())
    db.add(SessionMedia(session_id=session.id, kind="PHOTO", object_key=key, sha256="x", size_bytes=1))
    db.commit()
    return session, students


def test_match_job_writes_results_and_is_idempotent(db, monkeypatch):
    session, students = make_processing_session(db)
    # Face 1 = student 0 exactly. Face 2 is at distance 1.1 from student 1 (UNCERTAIN band).
    cos = 1 - 1.1**2 / 2
    face2 = cos * basis(1) + math.sqrt(1 - cos**2) * basis(10)
    # Face 3 matches nobody (far from everyone) → unmatched.
    fake = FakeEncoder([basis(0), face2.astype(np.float32), basis(20)])
    monkeypatch.setattr(match_job, "get_face_encoder", lambda: fake)

    match_job.run_match(str(session.id))

    db.expire_all()
    results = {r.student_id: r for r in db.exec(select(MatchResult)).all()}
    assert results[students[0].id].decision == "PRESENT"
    assert results[students[1].id].decision == "UNCERTAIN"
    assert results[students[2].id].decision == "NOT_DETECTED"
    assert results[students[0].id].crop_key and storage.exists(results[students[0].id].crop_key)
    assert len(db.exec(select(UnmatchedFace)).all()) == 1
    refreshed = db.get(AttendanceSession, session.id)
    assert refreshed.status == "REVIEW"
    assert refreshed.processing_ms is not None
    assert refreshed.config_snapshot["models"]["face"] == "fake-v1"

    # Running the same job again changes nothing (status is no longer PROCESSING).
    monkeypatch.setattr(match_job, "get_face_encoder", lambda: FakeEncoder([]))
    match_job.run_match(str(session.id))
    db.expire_all()
    assert db.exec(select(MatchResult).where(MatchResult.decision == "PRESENT")).first() is not None


def test_job_for_non_processing_session_is_noop(db, monkeypatch):
    session, _ = make_processing_session(db, status="REVIEW")
    monkeypatch.setattr(match_job, "get_face_encoder", lambda: FakeEncoder([basis(0)]))
    match_job.run_match(str(session.id))
    assert db.exec(select(MatchResult)).all() == []


def test_failure_callback_marks_failed_only_after_last_retry(db):
    session, _ = make_processing_session(db)
    job = SimpleNamespace(id="match-x", args=[str(session.id)], retries_left=2)

    callbacks.match_failed(job, None, RuntimeError, RuntimeError("boom"), None)
    db.expire_all()
    assert db.get(AttendanceSession, session.id).status == "PROCESSING"  # will retry

    job.retries_left = 0
    callbacks.match_failed(job, None, RuntimeError, RuntimeError("boom"), None)
    db.expire_all()
    failed = db.get(AttendanceSession, session.id)
    assert failed.status == "FAILED" and "boom" in failed.error


def test_retention_deletes_old_media(db):
    session, _ = make_processing_session(db, status="FINALIZED")
    session = db.get(AttendanceSession, session.id)
    session.finalized_at = utcnow() - timedelta(days=8)
    db.add(session)
    db.commit()
    media = db.exec(select(SessionMedia)).one()
    assert storage.exists(media.object_key)

    assert maintenance.apply_retention() == 1
    db.expire_all()
    media = db.get(SessionMedia, media.id)
    assert media.deleted_at is not None
    assert not storage.exists(media.object_key)


def test_unknown_session_id_is_noop(monkeypatch):
    monkeypatch.setattr(match_job, "get_face_encoder", lambda: FakeEncoder([]))
    match_job.run_match(str(uuid.uuid4()))  # does not raise


def test_student_with_open_face_request_is_not_marked_automatically(db, monkeypatch):
    """Even a perfect face match does not mark them present while a new photo is requested."""
    session, students = make_processing_session(db)
    db.add(
        FaceUpdateRequest(
            student_id=students[0].id, requested_by=session.teacher_id, class_id=session.class_id, reason="Old photo"
        )
    )
    db.commit()
    monkeypatch.setattr(match_job, "get_face_encoder", lambda: FakeEncoder([basis(0)]))

    match_job.run_match(str(session.id))

    db.expire_all()
    result = db.get(MatchResult, (session.id, students[0].id))
    assert result.decision == "NOT_DETECTED"
    assert result.face_update_pending is True
    assert result.has_biometrics is True  # they have samples; they are just not trusted now
    # Their face is still shown to the teacher, as a face that matched nobody.
    assert len(db.exec(select(UnmatchedFace)).all()) == 1


def test_new_face_photos_close_the_request(db, monkeypatch):
    session, students = make_processing_session(db)
    student = students[0]
    assert db.get(ConsentText, 1) is not None  # created by the test fixture
    db.add(Consent(student_id=student.id, version=1))
    db.add(
        FaceUpdateRequest(
            student_id=student.id, requested_by=session.teacher_id, class_id=session.class_id, reason="Old"
        )
    )
    job = BiometricJob(student_id=student.id, kind="FACE")
    db.add(job)
    db.commit()

    class GoodFaceEncoder:
        model_version = "fake-v1"

        def encode(self, image, min_face_px=24):
            return [DetectedFace((0, 0, 120, 120), basis(0), 0.95, 200.0)]

    monkeypatch.setattr(enroll_job, "get_face_encoder", lambda: GoodFaceEncoder())
    keys = []
    for i in range(3):
        key = f"enroll/{student.id}/{job.id}/{i}.jpg"
        storage.save(key, tiny_jpeg())
        keys.append(key)

    enroll_job.enroll_face(str(job.id), str(student.id), keys)

    db.expire_all()
    assert db.get(BiometricJob, job.id).status == "DONE"
    open_requests = db.exec(
        select(FaceUpdateRequest).where(
            FaceUpdateRequest.student_id == student.id, FaceUpdateRequest.resolved_at.is_(None)
        )
    ).all()
    assert open_requests == []


def test_checking_again_keeps_the_teachers_choices(db, monkeypatch):
    """After new photos, the AI suggestion is recomputed but the teacher's Present/Absent stays."""
    session, students = make_processing_session(db)
    db.add(
        MatchResult(
            session_id=session.id, student_id=students[0].id, decision="NOT_DETECTED", teacher_decision="ABSENT"
        )
    )
    db.commit()
    monkeypatch.setattr(match_job, "get_face_encoder", lambda: FakeEncoder([basis(0)]))

    match_job.run_match(str(session.id))

    db.expire_all()
    result = db.get(MatchResult, (session.id, students[0].id))
    assert result.decision == "PRESENT"  # new suggestion from the new photos
    assert result.teacher_decision == "ABSENT"  # the teacher's own choice is not thrown away
