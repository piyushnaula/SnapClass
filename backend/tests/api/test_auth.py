from tests.conftest import PASSWORD, make_user


def _login(client, email="t@x.com", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"login_id": email, "password": password})


def test_login_returns_tokens_and_user(client, db):
    make_user(db, "TEACHER", "t@x.com")
    response = _login(client, "T@X.com")  # emails are case-insensitive
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["role"] == "TEACHER"
    assert "password_hash" not in body["user"]


def test_wrong_password_and_unknown_email_give_same_error(client, db):
    make_user(db, "TEACHER", "t@x.com")
    wrong = _login(client, password="nope-nope")
    unknown = _login(client, email="ghost@x.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert "request_id" in wrong.json()["error"]


def test_inactive_user_cannot_login(client, db):
    user = make_user(db, "TEACHER", "t@x.com")
    user.is_active = False
    db.add(user)
    db.commit()
    assert _login(client).status_code == 401


def test_refresh_rotates_and_detects_reuse(client, db):
    make_user(db, "TEACHER", "t@x.com")
    first = _login(client).json()["refresh_token"]

    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200
    second = rotated.json()["refresh_token"]
    assert second != first

    # Reusing the old (revoked) token is treated as theft...
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert reuse.status_code == 401
    # ...so the newest token is revoked too.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": second}).status_code == 401


def test_logout_revokes_refresh_token(client, db):
    make_user(db, "TEACHER", "t@x.com")
    token = _login(client).json()["refresh_token"]
    assert client.post("/api/v1/auth/logout", json={"refresh_token": token}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": token}).status_code == 401


def test_login_rate_limit_per_ip(client, db):
    make_user(db, "TEACHER", "t@x.com")
    codes = [_login(client, password="wrong-password").status_code for _ in range(6)]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429


def test_protected_route_needs_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    bad = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401


def test_health_endpoints(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").status_code == 200
