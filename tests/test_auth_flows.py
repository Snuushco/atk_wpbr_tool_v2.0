import sqlite3
import time

import pytest

import app as atk_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "users.db"
    uploads = tmp_path / "uploads"
    monkeypatch.setitem(atk_app.app.config, "DATABASE_PATH", str(db_path))
    monkeypatch.setitem(atk_app.app.config, "UPLOAD_FOLDER", str(uploads))
    monkeypatch.setitem(atk_app.app.config, "TESTING", True)
    atk_app.init_db()
    with atk_app.app.test_client() as client:
        yield client


def _user_row(db_path, email):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    finally:
        conn.close()


def test_register_page_renders(client):
    res = client.get("/register")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "Gebruikersovereenkomst" in body
    assert "Privacyverklaring" in body


def test_invalid_login_returns_structured_error(client):
    res = client.post("/login", json={"email": "nobody@example.invalid", "password": "wrong"})
    assert res.status_code == 401
    assert res.json["success"] is False
    assert res.json["code"] == "INVALID_CREDENTIALS"


def test_register_success_creates_unverified_user_and_verified_login_after_token(client, monkeypatch):
    sent = {}

    def fake_send(email, token):
        sent["email"] = email
        sent["token"] = token
        return True

    monkeypatch.setattr(atk_app, "send_verification_email", fake_send)
    email = f"test_{int(time.time())}@example.invalid"
    res = client.post(
        "/register",
        json={
            "name": "Test Contact",
            "email": email.upper(),
            "password": "TestPassword123!",
            "vergunningnummer": "ND02255",
            "terms_accepted": True,
            "privacy_accepted": True,
        },
    )
    assert res.status_code == 200
    assert res.json["success"] is True
    assert sent["email"] == email
    row = _user_row(atk_app.app.config["DATABASE_PATH"], email)
    assert row is not None
    assert row["email_verified"] == 0
    assert row["verification_token"] == sent["token"]

    blocked = client.post("/login", json={"email": email, "password": "TestPassword123!"})
    assert blocked.status_code == 403
    assert blocked.json["code"] == "EMAIL_NOT_VERIFIED"

    verify = client.get(f"/verify-email/{sent['token']}")
    assert verify.status_code == 302
    login = client.post("/login", json={"email": email, "password": "TestPassword123!"})
    assert login.status_code == 200
    assert login.json["success"] is True


def test_register_email_failure_keeps_unverified_account(client, monkeypatch):
    monkeypatch.setattr(atk_app, "send_verification_email", lambda email, token: False)
    email = f"mailfail_{int(time.time())}@example.invalid"
    res = client.post(
        "/register",
        json={
            "name": "Test Contact",
            "email": email,
            "password": "TestPassword123!",
            "vergunningnummer": "BD01111",
            "terms_accepted": True,
            "privacy_accepted": True,
        },
    )
    assert res.status_code == 202
    assert res.json["code"] == "EMAIL_SEND_FAILED"
    row = _user_row(atk_app.app.config["DATABASE_PATH"], email)
    assert row is not None
    assert row["email_verified"] == 0
