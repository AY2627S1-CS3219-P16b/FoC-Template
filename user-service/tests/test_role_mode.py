from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


SECRET = "test-signing-secret"
PASSWORD = "StrongPass1!"


def make_client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'users.db'}", jwt_secret=SECRET)
    return TestClient(app), app


def register_and_login(client, number):
    email = f"e000000{number}@u.nus.edu"
    user = client.post("/api/v1/users/register", json={
        "email": email, "password": PASSWORD, "display_name": f"Student {number}",
    }).json()
    session = client.post("/api/v1/users/login", json={
        "email": email, "password": PASSWORD,
    }).json()
    return user, session["access_token"]


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def role_url(user):
    return f"/api/v1/users/{user['id']}/role-mode"


def test_active_user_can_switch_modes_and_login_returns_current_mode(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        user, token = register_and_login(client, 1)
        assert user["active_role_mode"] == "REQUESTER"
        for mode in ("COURIER", "REQUESTER", "COURIER"):
            response = client.patch(role_url(user), headers=headers(token), json={
                "active_role_mode": mode,
            })
            assert response.status_code == 200
            assert response.json()["active_role_mode"] == mode
            assert response.json()["id"] == user["id"]
            assert client.get(f"/api/v1/users/{user['id']}", headers=headers(token)).json()["active_role_mode"] == mode
        login = client.post("/api/v1/users/login", json={
            "email": user["email"], "password": PASSWORD,
        })
        assert login.status_code == 200
        assert login.json()["user"]["active_role_mode"] == "COURIER"
        assert jwt.decode(login.json()["access_token"], SECRET, algorithms=["HS256"])["active_role_mode"] == "COURIER"
        assert app.state.database.find_user_profile(user["id"])["active_role_mode"] == "COURIER"


@pytest.mark.parametrize("body", [
    {},
    {"active_role_mode": "ADMIN"},
    {"active_role_mode": "courier"},
    {"active_role_mode": None},
    {"active_role_mode": "COURIER", "auth_role": "ADMIN"},
])
def test_invalid_role_mode_does_not_change_account(tmp_path, body):
    client, app = make_client(tmp_path)
    with client:
        user, token = register_and_login(client, 1)
        response = client.patch(role_url(user), headers=headers(token), json=body)
        assert response.status_code == 422
        assert app.state.database.find_user_profile(user["id"])["active_role_mode"] == "REQUESTER"


@pytest.mark.parametrize("token", [None, "malformed", "bad-signature", "expired"])
def test_role_mode_requires_valid_token(tmp_path, token):
    client, app = make_client(tmp_path)
    with client:
        user, _ = register_and_login(client, 1)
        if token == "bad-signature":
            token = jwt.encode({"sub": user["id"], "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, "wrong", algorithm="HS256")
        elif token == "expired":
            token = jwt.encode({"sub": user["id"], "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, SECRET, algorithm="HS256")
        response = client.patch(role_url(user), headers=headers(token) if token else {}, json={
            "active_role_mode": "COURIER",
        })
        assert response.status_code == 401
        assert app.state.database.find_user_profile(user["id"])["active_role_mode"] == "REQUESTER"


def test_user_cannot_switch_another_users_mode(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        _, token = register_and_login(client, 1)
        other, _ = register_and_login(client, 2)
        response = client.patch(role_url(other), headers=headers(token), json={
            "active_role_mode": "COURIER",
        })
        assert response.status_code == 403
        assert app.state.database.find_user_profile(other["id"])["active_role_mode"] == "REQUESTER"


@pytest.mark.parametrize("account_status", ["SUSPENDED", "DISABLED"])
def test_inactive_user_cannot_switch_mode(tmp_path, account_status):
    client, app = make_client(tmp_path)
    with client:
        user, token = register_and_login(client, 1)
        app.state.database.update_account_status(user["email"], account_status)
        response = client.patch(role_url(user), headers=headers(token), json={
            "active_role_mode": "COURIER",
        })
        assert response.status_code == 401
        assert app.state.database.find_user_profile(user["id"])["active_role_mode"] == "REQUESTER"
