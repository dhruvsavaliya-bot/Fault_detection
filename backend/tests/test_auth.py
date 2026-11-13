"""tests/test_auth.py — registration, login, and account endpoints."""


def test_register_rejects_weak_password(client):
    resp = client.post("/auth/register", json={
        "username": "shortpass", "email": "shortpass@example.com", "password": "123",
    })
    assert resp.status_code == 400
    assert "6 characters" in resp.get_json()["error"]


def test_register_rejects_bad_email(client):
    resp = client.post("/auth/register", json={
        "username": "bademail", "email": "not-an-email", "password": "testpass123",
    })
    assert resp.status_code == 400


def test_register_rejects_missing_fields(client):
    resp = client.post("/auth/register", json={"username": "onlyusername"})
    assert resp.status_code == 400


def test_register_cannot_grant_admin_role(client):
    resp = client.post("/auth/register", json={
        "username": "wannabe_admin", "email": "wannabe@example.com",
        "password": "testpass123", "role": "admin",
    })
    assert resp.status_code == 201
    assert resp.get_json()["user"]["role"] == "operator"


def test_register_duplicate_username_rejected(client):
    payload = {"username": "dupe_user", "email": "dupe1@example.com", "password": "testpass123"}
    first = client.post("/auth/register", json=payload)
    assert first.status_code == 201

    payload["email"] = "dupe2@example.com"
    second = client.post("/auth/register", json=payload)
    assert second.status_code == 409


def test_login_success_and_failure(client):
    client.post("/auth/register", json={
        "username": "login_test", "email": "login_test@example.com", "password": "testpass123",
    })

    ok = client.post("/auth/login", json={"username": "login_test", "password": "testpass123"})
    assert ok.status_code == 200
    assert "token" in ok.get_json()

    wrong = client.post("/auth/login", json={"username": "login_test", "password": "wrongpass"})
    assert wrong.status_code == 401

    nobody = client.post("/auth/login", json={"username": "nobody_here", "password": "whatever"})
    assert nobody.status_code == 401


def test_me_requires_auth(client, auth_token):
    anon = client.get("/auth/me")
    assert anon.status_code == 401

    authed = client.get("/auth/me", headers=auth_token)
    assert authed.status_code == 200
    assert authed.get_json()["username"].startswith("test_operator_")


def test_change_password_flow(client, auth_token):
    username = client.get("/auth/me", headers=auth_token).get_json()["username"]

    wrong_old = client.put("/auth/change-password", headers=auth_token, json={
        "old_password": "not-the-real-password", "new_password": "newpass123",
    })
    assert wrong_old.status_code == 403

    too_short = client.put("/auth/change-password", headers=auth_token, json={
        "old_password": "testpass123", "new_password": "abc",
    })
    assert too_short.status_code == 400

    ok = client.put("/auth/change-password", headers=auth_token, json={
        "old_password": "testpass123", "new_password": "newpass123",
    })
    assert ok.status_code == 200

    relogin = client.post("/auth/login", json={"username": username, "password": "newpass123"})
    assert relogin.status_code == 200
