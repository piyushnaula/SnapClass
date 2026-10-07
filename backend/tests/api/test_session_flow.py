"""The main teacher + student journey, end to end through the HTTP API.

The ML worker is not run here (see tests/worker); we write its results
directly to the database, the same way the worker would.
"""

import uuid

from sqlmodel import select

from snapclass.models import AttendanceRecord, AttendanceSession, AuditLog, FaceEmbedding, MatchResult
from tests.conftest import PASSWORD, login, make_user, tiny_jpeg

API = "/api/v1"


def register_student(client, student_id: str, name: str) -> dict:
    """A student creates an account with their student ID (and is signed in)."""
    response = client.post(
        f"{API}/auth/register", json={"student_id": student_id, "full_name": name, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {"id": body["user"]["id"], "headers": {"Authorization": f"Bearer {body['access_token']}"}}


def setup_class_with_students(client, db, n_students=2):
    make_user(db, "TEACHER", "t@x.com")
    teacher = login(client, "t@x.com")
    class_id = client.post(
        f"{API}/classes", json={"subject": "DBMS", "section": "A", "semester": 5}, headers=teacher
    ).json()["id"]
    code = client.post(f"{API}/classes/{class_id}/join-codes", json={}, headers=teacher).json()["code"]

    students = []
    for i in range(n_students):
        student = register_student(client, f"23cse{i:03d}", f"Student {i}")
        joined = client.post(f"{API}/join/{code}", headers=student["headers"])
        assert joined.status_code == 200, joined.text
        students.append(student)
    return teacher, class_id, code, students


def test_register_and_sign_in_with_student_id(client, db):
    student = register_student(client, " 23cse099 ", "Asha   Rawat")
    me = client.get(f"{API}/auth/me", headers=student["headers"]).json()
    assert me["roll_no"] == "23CSE099" and me["full_name"] == "Asha Rawat" and me["email"] is None

    # Sign in with the student ID (any letter case).
    signed_in = client.post(f"{API}/auth/login", json={"login_id": "23Cse099", "password": PASSWORD})
    assert signed_in.status_code == 200

    # The same student ID cannot be registered twice.
    again = client.post(
        f"{API}/auth/register", json={"student_id": "23CSE099", "full_name": "Someone Else", "password": PASSWORD}
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "STUDENT_ID_TAKEN"

    bad_id = client.post(
        f"{API}/auth/register", json={"student_id": "bad id!", "full_name": "X Y", "password": PASSWORD}
    )
    assert bad_id.status_code == 422


def test_join_code_flow(client, db):
    teacher, class_id, code, students = setup_class_with_students(client, db)
    info = client.get(f"{API}/join/{code}").json()
    assert info == {"subject": "DBMS", "section": "A", "semester": 5}

    roster = client.get(f"{API}/classes/{class_id}/students", headers=teacher).json()
    assert [s["roll_no"] for s in roster] == ["23CSE000", "23CSE001"]  # upper-cased
    assert "embedding" not in roster[0]

    # Joining needs a signed-in student; joining twice is harmless; teachers cannot join.
    assert client.post(f"{API}/join/{code}").status_code == 401
    again = client.post(f"{API}/join/{code}", headers=students[0]["headers"]).json()
    assert again["already_joined"] is True
    assert client.post(f"{API}/join/{code}", headers=teacher).status_code == 403
    assert client.get(f"{API}/join/doesnotexist").status_code == 404


def test_biometrics_need_consent(client, db, queued):
    _, _, _, students = setup_class_with_students(client, db, 1)
    student = students[0]["headers"]
    photos = [("photos", (f"p{i}.jpg", tiny_jpeg(), "image/jpeg")) for i in range(3)]

    assert client.post(f"{API}/me/biometrics/face", files=photos, headers=student).status_code == 403

    consent = client.get(f"{API}/consent/current", headers=student).json()
    assert consent["accepted"] is False
    assert client.post(f"{API}/consent", json={"version": consent["version"]}, headers=student).status_code == 204

    response = client.post(f"{API}/me/biometrics/face", files=photos, headers=student)
    assert response.status_code == 202
    assert queued[-1][0] == "FACE" and len(queued[-1][3]) == 3

    too_few = client.post(f"{API}/me/biometrics/face", files=photos[:2], headers=student)
    assert too_few.status_code == 400


def test_fake_image_is_rejected(client, db):
    teacher, class_id, _, _ = setup_class_with_students(client, db, 1)
    session_id = client.post(
        f"{API}/classes/{class_id}/sessions", json={"session_date": "2026-10-07", "period": 1}, headers=teacher
    ).json()["id"]
    fake = [("photos", ("class.jpg", b"this is not an image at all", "image/jpeg"))]
    response = client.post(f"{API}/sessions/{session_id}/media", files=fake, headers=teacher)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_full_session_flow(client, db, queued):
    teacher, class_id, _, students = setup_class_with_students(client, db, 2)
    s0, s1 = uuid.UUID(students[0]["id"]), uuid.UUID(students[1]["id"])

    # Create a session; a duplicate (same class/date/period) is refused.
    body = {"session_date": "2026-10-07", "period": 2}
    session_id = client.post(f"{API}/classes/{class_id}/sessions", json=body, headers=teacher).json()["id"]
    assert client.post(f"{API}/classes/{class_id}/sessions", json=body, headers=teacher).status_code == 409

    # Cannot process before uploading.
    assert client.post(f"{API}/sessions/{session_id}/process", headers=teacher).status_code == 409

    upload = client.post(
        f"{API}/sessions/{session_id}/media", files=[("photos", ("c.jpg", tiny_jpeg(), "image/jpeg"))], headers=teacher
    )
    assert upload.status_code == 200
    assert upload.json()["status"] == "UPLOADED"

    # Process is idempotent: first call queues (202), second does nothing new (200).
    first = client.post(f"{API}/sessions/{session_id}/process", headers=teacher)
    second = client.post(f"{API}/sessions/{session_id}/process", headers=teacher)
    assert (first.status_code, second.status_code) == (202, 200)
    assert [c for c in queued if c[0] == "match"] == [("match", session_id)]

    # --- pretend the worker ran: s0 clearly present, s1 uncertain ---
    sid = uuid.UUID(session_id)
    db.add(MatchResult(session_id=sid, student_id=s0, decision="PRESENT", face_distance=0.8, fused_score=0.68))
    db.add(MatchResult(session_id=sid, student_id=s1, decision="UNCERTAIN", face_distance=1.1, fused_score=0.4))
    session = db.get(AttendanceSession, sid)
    session.status = "REVIEW"
    db.add(session)
    db.commit()

    detail = client.get(f"{API}/sessions/{session_id}", headers=teacher).json()
    assert detail["summary"]["present"] == 1 and detail["summary"]["needs_review"] == 1

    # Finalize is blocked until the uncertain student is decided.
    blocked = client.post(f"{API}/sessions/{session_id}/finalize", headers=teacher)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "REVIEW_INCOMPLETE"

    assert (
        client.patch(
            f"{API}/sessions/{session_id}/results/{s1}", json={"teacher_decision": "ABSENT"}, headers=teacher
        ).status_code
        == 204
    )
    final = client.post(f"{API}/sessions/{session_id}/finalize", headers=teacher)
    assert final.status_code == 200 and final.json()["status"] == "FINALIZED"

    db.expire_all()
    records = {r.student_id: r for r in db.exec(select(AttendanceRecord)).all()}
    assert (records[s0].status, records[s0].source) == ("PRESENT", "AI_CONFIRMED")
    assert (records[s1].status, records[s1].source) == ("ABSENT", "TEACHER_OVERRIDE")

    # Cannot finalize twice or toggle after finalizing.
    assert client.post(f"{API}/sessions/{session_id}/finalize", headers=teacher).status_code == 409
    assert (
        client.patch(
            f"{API}/sessions/{session_id}/results/{s1}", json={"teacher_decision": "PRESENT"}, headers=teacher
        ).status_code
        == 409
    )

    # Correction needs a reason and is audited.
    no_reason = client.patch(
        f"{API}/sessions/{session_id}/attendance/{s1}", json={"status": "PRESENT"}, headers=teacher
    )
    assert no_reason.status_code == 422
    fixed = client.patch(
        f"{API}/sessions/{session_id}/attendance/{s1}",
        json={"status": "PRESENT", "reason": "Came in late"},
        headers=teacher,
    )
    assert fixed.status_code == 204
    audit = db.exec(select(AuditLog).where(AuditLog.action == "ATTENDANCE_CORRECT")).one()
    assert audit.before["status"] == "ABSENT" and audit.after["status"] == "PRESENT" and audit.reason == "Came in late"

    # Report: JSON and CSV.
    report = client.get(f"{API}/classes/{class_id}/report", headers=teacher).json()
    assert {row["pct"] for row in report["rows"]} == {100.0}
    csv_response = client.get(f"{API}/classes/{class_id}/report?format=csv", headers=teacher)
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "23CSE000" in csv_response.text

    # Student sees only their own attendance.
    mine = client.get(f"{API}/me/attendance", headers=students[0]["headers"]).json()
    assert mine[0]["present"] == 1 and mine[0]["total"] == 1


def test_erasing_biometrics_keeps_attendance(client, db):
    _, _, _, students = setup_class_with_students(client, db, 1)
    student_id = uuid.UUID(students[0]["id"])
    db.add(FaceEmbedding(student_id=student_id, embedding=[0.1] * 128, quality=0.9, model_ver="test"))
    db.commit()

    assert client.delete(f"{API}/me/biometrics", headers=students[0]["headers"]).status_code == 204
    db.expire_all()
    assert db.exec(select(FaceEmbedding).where(FaceEmbedding.student_id == student_id)).first() is None
    assert db.exec(select(AuditLog).where(AuditLog.action == "BIOMETRIC_DELETE")).first() is not None
    status = client.get(f"{API}/me/biometrics", headers=students[0]["headers"]).json()
    assert status["face_samples"] == 0 and status["consent_current"] is False
