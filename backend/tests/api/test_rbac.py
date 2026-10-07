"""Access control: roles (RBAC) and other people's data (IDOR)."""

from tests.conftest import login, make_user

CLASS = {"subject": "DBMS", "section": "A", "semester": 5}


def test_student_cannot_create_class(client, db):
    make_user(db, "STUDENT", "s@x.com", roll_no="S1")
    response = client.post("/api/v1/classes", json=CLASS, headers=login(client, "s@x.com"))
    assert response.status_code == 403


def test_teacher_cannot_use_admin_endpoints(client, db):
    make_user(db, "TEACHER", "t@x.com")
    assert client.get("/api/v1/admin/metrics", headers=login(client, "t@x.com")).status_code == 403


def test_teacher_b_gets_404_for_teacher_a_data(client, db):
    make_user(db, "TEACHER", "a@x.com")
    make_user(db, "TEACHER", "b@x.com")
    a, b = login(client, "a@x.com"), login(client, "b@x.com")

    class_id = client.post("/api/v1/classes", json=CLASS, headers=a).json()["id"]
    session_id = client.post(
        f"/api/v1/classes/{class_id}/sessions", json={"session_date": "2026-10-07", "period": 1}, headers=a
    ).json()["id"]

    # 404 (not 403) so B cannot even tell that these ids exist.
    assert client.get(f"/api/v1/classes/{class_id}", headers=b).status_code == 404
    assert client.get(f"/api/v1/classes/{class_id}/report", headers=b).status_code == 404
    assert client.post(f"/api/v1/classes/{class_id}/join-codes", json={}, headers=b).status_code == 404
    assert client.get(f"/api/v1/sessions/{session_id}", headers=b).status_code == 404
    assert client.post(f"/api/v1/sessions/{session_id}/finalize", headers=b).status_code == 404
    assert client.get("/api/v1/classes", headers=b).json() == []


def test_admin_creates_and_deactivates_teacher(client, db):
    make_user(db, "ADMIN", "admin@x.com")
    admin = login(client, "admin@x.com")
    created = client.post(
        "/api/v1/admin/teachers",
        json={"email": "new@x.com", "full_name": "New Teacher", "password": "a-strong-password"},
        headers=admin,
    )
    assert created.status_code == 201
    teacher_id = created.json()["id"]
    login(client, "new@x.com", "a-strong-password")  # can log in

    off = client.patch(f"/api/v1/admin/users/{teacher_id}", json={"is_active": False}, headers=admin)
    assert off.status_code == 200
    blocked = client.post("/api/v1/auth/login", json={"login_id": "new@x.com", "password": "a-strong-password"})
    assert blocked.status_code == 401

    actions = [row["action"] for row in client.get("/api/v1/admin/audit", headers=admin).json()]
    assert "ROLE_CHANGE" in actions and "USER_STATUS_CHANGE" in actions


def test_admin_settings_validation(client, db):
    make_user(db, "ADMIN", "admin@x.com")
    admin = login(client, "admin@x.com")
    bad = client.put(
        "/api/v1/admin/settings", json={"thresholds": {"face_accept": 1.5, "face_reject": 1.0}}, headers=admin
    )
    assert bad.status_code == 400
    good = client.put(
        "/api/v1/admin/settings", json={"thresholds": {"face_accept": 1.0}, "retention_days": 3}, headers=admin
    )
    assert good.status_code == 200
    assert good.json()["thresholds"]["face_accept"] == 1.0
    assert good.json()["retention"]["days"] == 3
