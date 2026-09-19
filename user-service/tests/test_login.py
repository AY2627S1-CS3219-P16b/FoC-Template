from datetime import datetime, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


JWT_SECRET = "test-signing-secret"
PASSWORD = "StrongPass1!"


def make_client(tmp_path):
    app = create_app(
        f"sqlite:///{tmp_path / 'users.db'}",
        jwt_secret=JWT_SECRET,
    )
    return TestClient(app), app


def register(client):
    response = client.post(
        "/api/v1/users/register",
        json={
            "email": "e0123456@u.nus.edu",
            "password": PASSWORD,
            "display_name": "NUS Student",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_active_user_can_login_and_receives_signed_claims(tmp_path):
    client, _ = make_client(tmp_path)
    with client:
        registered_user = register(client)
        response = client.post(
            "/api/v1/users/login",
            json={"email": "E0123456@u.nus.edu", "password": PASSWORD},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["user"]["active_role_mode"] == "REQUESTER"

    claims = jwt.decode(body["access_token"], JWT_SECRET, algorithms=["HS256"])
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(body["access_token"], "wrong-secret", algorithms=["HS256"])
    assert claims["sub"] == registered_user["id"]
    assert claims["user_id"] == registered_user["id"]
    assert claims["email"] == "e0123456@u.nus.edu"
    assert claims["auth_role"] == "USER"
    assert claims["active_role_mode"] == "REQUESTER"
    assert claims["account_status"] == "ACTIVE"
    assert datetime.fromtimestamp(claims["exp"], timezone.utc) > datetime.now(
        timezone.utc
    )


@pytest.mark.parametrize(
    "email,password",
    [
        ("unknown@u.nus.edu", PASSWORD),
        ("e0123456@u.nus.edu", "Incorrect1!"),
    ],
)
def test_unknown_email_and_wrong_password_return_same_error(tmp_path, email, password):
    client, _ = make_client(tmp_path)
    with client:
        register(client)
        response = client.post(
            "/api/v1/users/login", json={"email": email, "password": password}
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}


@pytest.mark.parametrize("account_status", ["SUSPENDED", "DISABLED"])
def test_non_active_accounts_cannot_login(tmp_path, account_status):
    client, app = make_client(tmp_path)
    with client:
        register(client)
        app.state.database.update_account_status(
            "e0123456@u.nus.edu", account_status
        )
        response = client.post(
            "/api/v1/users/login",
            json={"email": "e0123456@u.nus.edu", "password": PASSWORD},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}


def test_login_rejects_missing_credentials(tmp_path):
    client, _ = make_client(tmp_path)
    with client:
        response = client.post("/api/v1/users/login", json={})

    assert response.status_code == 422
    assert {error["field"] for error in response.json()["errors"]} == {
        "email",
        "password",
    }
