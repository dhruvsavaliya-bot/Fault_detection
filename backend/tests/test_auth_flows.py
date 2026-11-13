"""tests/test_auth_flows.py — email verification and password reset.

mailer.send_email logs instead of actually sending when SMTP isn't
configured (true in tests), so these tests monkeypatch routes.auth.send_email
to capture the outgoing message and pull the raw token out of its link —
the same way a real recipient would click it.
"""

import re
import pytest
import routes.auth as auth_module
from flask_jwt_extended import create_access_token
from app import app as flask_app
from database import db, User


@pytest.fixture()
def sent_emails(monkeypatch):
    messages = []

    def fake_send(to_email, subject, body):
        messages.append({"to": to_email, "subject": subject, "body": body})
        return True

    monkeypatch.setattr(auth_module, "send_email", fake_send)
    return messages


def _extract_token(body):
    m = re.search(r"[?&]token=([^\s&]+)", body)
    assert m, f"no token found in email body:\n{body}"
    return m.group(1)


def _register(client, username):
    resp = client.post("/auth/register", json={
        "username": username, "email": f"{username}@example.com", "password": "testpass123",
    })
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


# ── Email verification ───────────────────────────────────────────────────────

def test_register_sends_verification_email_and_starts_unverified(client, sent_emails):
    reg = _register(client, "verify_flow_user")
    assert len(sent_emails) == 1
    assert "Verify" in sent_emails[0]["subject"]
    assert reg["user"]["email_verified"] is False

    headers = {"Authorization": f"Bearer {reg['token']}"}
    me = client.get("/auth/me", headers=headers).get_json()
    assert me["email_verified"] is False


def test_verify_email_link_marks_account_verified(client, sent_emails):
    reg = _register(client, "verify_flow_user2")
    token = _extract_token(sent_emails[0]["body"])

    resp = client.get(f"/auth/verify-email?token={token}")
    assert resp.status_code == 302
    assert "verify=success" in resp.location

    headers = {"Authorization": f"Bearer {reg['token']}"}
    me = client.get("/auth/me", headers=headers).get_json()
    assert me["email_verified"] is True


def test_verify_email_already_verified_redirects_distinctly(client, sent_emails):
    _register(client, "verify_flow_user3")
    token = _extract_token(sent_emails[0]["body"])

    client.get(f"/auth/verify-email?token={token}")
    second = client.get(f"/auth/verify-email?token={token}")
    assert "verify=already" in second.location


def test_verify_email_bad_token_redirects_expired(client):
    resp = client.get("/auth/verify-email?token=not-a-real-token")
    assert "verify=expired" in resp.location


def test_resend_verification_noop_once_verified(client, sent_emails):
    reg = _register(client, "verify_flow_user4")
    headers = {"Authorization": f"Bearer {reg['token']}"}
    token = _extract_token(sent_emails[0]["body"])
    client.get(f"/auth/verify-email?token={token}")

    resend = client.post("/auth/resend-verification", headers=headers)
    assert resend.status_code == 200
    assert resend.get_json()["message"] == "Already verified"
    assert len(sent_emails) == 1  # no second email sent


def test_resend_verification_sends_new_token(client, sent_emails):
    reg = _register(client, "verify_flow_user5")
    headers = {"Authorization": f"Bearer {reg['token']}"}

    resend = client.post("/auth/resend-verification", headers=headers)
    assert resend.status_code == 200
    assert len(sent_emails) == 2  # register email + resend email

    new_token = _extract_token(sent_emails[1]["body"])
    verify = client.get(f"/auth/verify-email?token={new_token}")
    assert "verify=success" in verify.location


def test_user_without_verification_record_is_grandfathered_in(client):
    """An account that existed before this feature shipped (no
    EmailVerification row at all) must not be retroactively locked out."""
    with flask_app.app_context():
        user = User(username="pre_existing_user", email="pre_existing@example.com",
                    password_hash="x", role="operator")
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id))

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).get_json()
    assert me["email_verified"] is True


# ── Password reset ───────────────────────────────────────────────────────────

def test_forgot_password_sends_email_for_existing_user(client, sent_emails):
    _register(client, "reset_flow_user")
    resp = client.post("/auth/forgot-password", json={"email": "reset_flow_user@example.com"})
    assert resp.status_code == 200
    reset_emails = [m for m in sent_emails if "Reset" in m["subject"]]
    assert len(reset_emails) == 1


def test_forgot_password_same_response_for_unknown_email(client, sent_emails):
    known = client.post("/auth/forgot-password", json={"email": "nobody_at_all@example.com"})
    assert known.status_code == 200
    assert "a reset link has been sent" in known.get_json()["message"]
    assert len([m for m in sent_emails if "Reset" in m["subject"]]) == 0


def test_full_password_reset_flow(client, sent_emails):
    _register(client, "reset_flow_user2")
    client.post("/auth/forgot-password", json={"email": "reset_flow_user2@example.com"})
    reset_email = next(m for m in sent_emails if "Reset" in m["subject"])
    token = _extract_token(reset_email["body"])

    reset = client.post("/auth/reset-password", json={"token": token, "new_password": "brandnewpass456"})
    assert reset.status_code == 200

    old_login = client.post("/auth/login", json={"username": "reset_flow_user2", "password": "testpass123"})
    assert old_login.status_code == 401

    new_login = client.post("/auth/login", json={"username": "reset_flow_user2", "password": "brandnewpass456"})
    assert new_login.status_code == 200


def test_reset_password_token_is_single_use(client, sent_emails):
    _register(client, "reset_flow_user3")
    client.post("/auth/forgot-password", json={"email": "reset_flow_user3@example.com"})
    token = _extract_token(next(m for m in sent_emails if "Reset" in m["subject"])["body"])

    first = client.post("/auth/reset-password", json={"token": token, "new_password": "firstnewpass1"})
    assert first.status_code == 200

    second = client.post("/auth/reset-password", json={"token": token, "new_password": "secondnewpass2"})
    assert second.status_code == 400


def test_reset_password_rejects_invalid_token(client):
    resp = client.post("/auth/reset-password", json={"token": "garbage", "new_password": "whatever123"})
    assert resp.status_code == 400


def test_reset_password_rejects_short_password(client, sent_emails):
    _register(client, "reset_flow_user4")
    client.post("/auth/forgot-password", json={"email": "reset_flow_user4@example.com"})
    token = _extract_token(next(m for m in sent_emails if "Reset" in m["subject"])["body"])

    resp = client.post("/auth/reset-password", json={"token": token, "new_password": "abc"})
    assert resp.status_code == 400
