"""Teacher asks a student for a new face photo; photo limit per lecture."""

from sqlmodel import select

from snapclass.models import AuditLog
from tests.api.test_session_flow import API, setup_class_with_students
from tests.conftest import login, make_user, tiny_jpeg


def request_url(class_id, student_id):
    return f"{API}/classes/{class_id}/students/{student_id}/face-update-request"


def test_teacher_requests_and_cancels_new_face_photo(client, db):
    teacher, class_id, _, students = setup_class_with_students(client, db, 2)
    s0 = students[0]

    first = client.post(
        request_url(class_id, s0["id"]), json={"reason": "Not recognised in class photos"}, headers=teacher
    )
    assert first.status_code == 201
    # Asking again does not create a second request.
    second = client.post(request_url(class_id, s0["id"]), json={"reason": "Again"}, headers=teacher)
    assert second.json()["id"] == first.json()["id"]

    roster = {s["id"]: s for s in client.get(f"{API}/classes/{class_id}/students", headers=teacher).json()}
    assert roster[s0["id"]]["face_update_requested"] is True
    assert roster[students[1]["id"]]["face_update_requested"] is False

    # The student sees who asked, for which subject, and why.
    seen = client.get(f"{API}/me/biometrics", headers=s0["headers"]).json()["face_update_request"]
    assert seen["reason"] == "Not recognised in class photos"
    assert seen["subject"] == "DBMS"

    # The teacher can withdraw the request.
    assert client.delete(request_url(class_id, s0["id"]), headers=teacher).status_code == 204
    assert client.get(f"{API}/me/biometrics", headers=s0["headers"]).json()["face_update_request"] is None

    actions = {a.action for a in db.exec(select(AuditLog)).all()}
    assert {"FACE_UPDATE_REQUESTED", "FACE_UPDATE_CANCELLED"} <= actions


def test_only_the_class_teacher_can_request(client, db):
    _, class_id, _, students = setup_class_with_students(client, db, 1)
    make_user(db, "TEACHER", "other@x.com")
    other = login(client, "other@x.com")
    response = client.post(request_url(class_id, students[0]["id"]), json={"reason": "Not recognised"}, headers=other)
    assert response.status_code == 404  # other teachers cannot even see this class
    # Students cannot ask on someone's behalf.
    as_student = client.post(
        request_url(class_id, students[0]["id"]), json={"reason": "x" * 5}, headers=students[0]["headers"]
    )
    assert as_student.status_code == 403


def test_up_to_ten_class_photos(client, db):
    teacher, class_id, _, _ = setup_class_with_students(client, db, 1)
    session_id = client.post(
        f"{API}/classes/{class_id}/sessions", json={"session_date": "2026-10-07", "period": 1}, headers=teacher
    ).json()["id"]
    ten = [("photos", (f"c{i}.jpg", tiny_jpeg(), "image/jpeg")) for i in range(10)]
    ok = client.post(f"{API}/sessions/{session_id}/media", files=ten, headers=teacher)
    assert ok.status_code == 200 and ok.json()["photo_count"] == 10

    one_more = client.post(
        f"{API}/sessions/{session_id}/media", files=[("photos", ("c.jpg", tiny_jpeg(), "image/jpeg"))], headers=teacher
    )
    assert one_more.status_code == 400
