"""Adding or removing class photos during review, then checking again."""

import uuid

from sqlmodel import col, delete

from snapclass.models import AttendanceSession, MatchResult
from tests.api.test_session_flow import API, setup_class_with_students
from tests.conftest import tiny_jpeg


def photo(name="c.jpg"):
    return [("photos", (name, tiny_jpeg(), "image/jpeg"))]


def to_review(db, session_id, results):
    """Pretend the worker finished: write results and move the session to REVIEW."""
    sid = uuid.UUID(session_id)
    db.execute(delete(MatchResult).where(col(MatchResult.session_id) == sid))
    for student_id, decision, teacher_decision in results:
        db.add(
            MatchResult(
                session_id=sid, student_id=uuid.UUID(student_id), decision=decision, teacher_decision=teacher_decision
            )
        )
    session = db.get(AttendanceSession, sid)
    session.status = "REVIEW"
    db.add(session)
    db.commit()


def test_add_photos_during_review_and_check_again(client, db, queued):
    teacher, class_id, _, students = setup_class_with_students(client, db, 2)
    s0, s1 = students[0]["id"], students[1]["id"]
    sid = client.post(
        f"{API}/classes/{class_id}/sessions", json={"session_date": "2026-10-07", "period": 1}, headers=teacher
    ).json()["id"]
    client.post(f"{API}/sessions/{sid}/media", files=photo(), headers=teacher)
    client.post(f"{API}/sessions/{sid}/process", headers=teacher)
    # s0 was not found; the teacher already marked s1 absent by hand.
    to_review(db, sid, [(s0, "NOT_DETECTED", None), (s1, "UNCERTAIN", "ABSENT")])

    # Teacher adds another photo while reviewing → the lecture waits for a new check.
    added = client.post(f"{API}/sessions/{sid}/media", files=photo("back-row.jpg"), headers=teacher)
    assert added.status_code == 200
    detail = added.json()
    assert detail["status"] == "UPLOADED" and detail["photo_count"] == 2
    assert all(m["url"] for m in detail["media"])

    # The teacher can see their own class photo through the signed link.
    assert client.get(detail["media"][0]["url"]).status_code == 200

    # Check again: queued a second time, and the teacher's choice for s1 is kept.
    again = client.post(f"{API}/sessions/{sid}/process", headers=teacher)
    assert again.status_code == 202
    assert [c for c in queued if c[0] == "match"] == [("match", sid), ("match", sid)]
    db.expire_all()
    assert db.get(MatchResult, (uuid.UUID(sid), uuid.UUID(s1))).teacher_decision == "ABSENT"


def test_remove_photos_and_clear_choices(client, db, queued):
    teacher, class_id, _, students = setup_class_with_students(client, db, 1)
    s0 = students[0]["id"]
    sid = client.post(
        f"{API}/classes/{class_id}/sessions", json={"session_date": "2026-10-07", "period": 2}, headers=teacher
    ).json()["id"]
    two = [("photos", ("a.jpg", tiny_jpeg(), "image/jpeg")), ("photos", ("b.jpg", tiny_jpeg(), "image/jpeg"))]
    media = client.post(f"{API}/sessions/{sid}/media", files=two, headers=teacher).json()["media"]
    client.post(f"{API}/sessions/{sid}/process", headers=teacher)
    to_review(db, sid, [(s0, "UNCERTAIN", "PRESENT")])

    # Remove a blurry photo during review.
    removed = client.delete(f"{API}/sessions/{sid}/media/{media[0]['id']}", headers=teacher)
    assert removed.status_code == 200
    assert removed.json()["status"] == "UPLOADED" and removed.json()["photo_count"] == 1

    # Check again and ask for a fresh start: the teacher's choices are cleared.
    assert client.post(f"{API}/sessions/{sid}/process?clear_decisions=true", headers=teacher).status_code == 202
    db.expire_all()
    assert db.get(MatchResult, (uuid.UUID(sid), uuid.UUID(s0))).teacher_decision is None

    # Removing the last photo while not checking → back to "not started".
    to_review(db, sid, [(s0, "NOT_DETECTED", None)])
    last = client.delete(f"{API}/sessions/{sid}/media/{media[1]['id']}", headers=teacher)
    assert last.json()["status"] == "CREATED" and last.json()["photo_count"] == 0


def test_photos_are_locked_while_checking_and_after_saving(client, db, queued):
    teacher, class_id, _, students = setup_class_with_students(client, db, 1)
    sid = client.post(
        f"{API}/classes/{class_id}/sessions", json={"session_date": "2026-10-07", "period": 3}, headers=teacher
    ).json()["id"]
    media_id = client.post(f"{API}/sessions/{sid}/media", files=photo(), headers=teacher).json()["media"][0]["id"]
    client.post(f"{API}/sessions/{sid}/process", headers=teacher)

    while_checking = client.post(f"{API}/sessions/{sid}/media", files=photo(), headers=teacher)
    assert while_checking.status_code == 409 and while_checking.json()["error"]["code"] == "MEDIA_LOCKED"

    to_review(db, sid, [(students[0]["id"], "PRESENT", None)])
    assert client.post(f"{API}/sessions/{sid}/finalize", headers=teacher).status_code == 200
    assert client.post(f"{API}/sessions/{sid}/media", files=photo(), headers=teacher).status_code == 409
    assert client.delete(f"{API}/sessions/{sid}/media/{media_id}", headers=teacher).status_code == 409


def test_other_teacher_cannot_remove_photos(client, db):
    from tests.conftest import login, make_user

    teacher, class_id, _, _ = setup_class_with_students(client, db, 1)
    sid = client.post(
        f"{API}/classes/{class_id}/sessions", json={"session_date": "2026-10-07", "period": 4}, headers=teacher
    ).json()["id"]
    media_id = client.post(f"{API}/sessions/{sid}/media", files=photo(), headers=teacher).json()["media"][0]["id"]
    make_user(db, "TEACHER", "other@x.com")
    other = login(client, "other@x.com")
    assert client.delete(f"{API}/sessions/{sid}/media/{media_id}", headers=other).status_code == 404
