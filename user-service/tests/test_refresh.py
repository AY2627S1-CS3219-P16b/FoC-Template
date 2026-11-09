from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.database import refresh_tokens
from app.main import create_app


PASSWORD = "StrongPass1!"
EMAIL = "e0123456@u.nus.edu"
EXPIRED = {"detail": "Your session has expired. Please log in again."}


def make_client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'users.db'}")
    return TestClient(app), app


def register_and_login(client, email=EMAIL):
    response = client.post(
        "/api/v1/users/register",
        json={"email": email, "password": PASSWORD, "display_name": "NUS Student"},
    )
    assert response.status_code == 201
    response = client.post("/api/v1/users/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return response.json()


def refresh(client, token):
    return client.post("/api/v1/users/refresh", json={"refresh_token": token})


def test_login_returns_refresh_token(tmp_path):
    client, _ = make_client(tmp_path)
    with client:
        session = register_and_login(client)

    assert session["expires_in"] == 15 * 60
    assert session["refresh_expires_in"] == 7 * 24 * 60 * 60
    assert len(session["refresh_token"]) >= 40


def test_refresh_token_is_stored_hashed(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        session = register_and_login(client)
        with app.state.database.engine.connect() as connection:
            hashes = [row.token_hash for row in connection.execute(refresh_tokens.select())]

    assert len(hashes) == 1
    assert hashes[0] != session["refresh_token"]


def test_refresh_issues_new_tokens_and_rotates(tmp_path, jwt_public_key):
    client, _ = make_client(tmp_path)
    with client:
        session = register_and_login(client)
        response = refresh(client, session["refresh_token"])
        assert response.status_code == 200
        body = response.json()
        reused = refresh(client, session["refresh_token"])
        again = refresh(client, body["refresh_token"])

    assert body["refresh_token"] != session["refresh_token"]
    claims = jwt.decode(body["access_token"], jwt_public_key, algorithms=["RS256"])
    assert claims["sub"] == session["user"]["id"]
    assert claims["account_status"] == "ACTIVE"
    assert body["user"]["email"] == EMAIL
    assert reused.status_code == 401
    assert reused.json() == EXPIRED
    assert again.status_code == 200


def test_new_access_token_works_on_protected_endpoint(tmp_path):
    client, _ = make_client(tmp_path)
    with client:
        session = register_and_login(client)
        body = refresh(client, session["refresh_token"]).json()
        response = client.get(
            f"/api/v1/users/{session['user']['id']}",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )

    assert response.status_code == 200


def test_refresh_reflects_current_role(tmp_path, jwt_public_key):
    client, app = make_client(tmp_path)
    with client:
        session = register_and_login(client)
        app.state.database.bootstrap_first_admin(EMAIL)
        body = refresh(client, session["refresh_token"]).json()

    claims = jwt.decode(body["access_token"], jwt_public_key, algorithms=["RS256"])
    assert claims["auth_role"] == "ADMIN"
    assert body["user"]["auth_role"] == "ADMIN"


@pytest.mark.parametrize("token", ["", "unknown-token", "x" * 201])
def test_invalid_refresh_token_is_rejected(tmp_path, token):
    client, _ = make_client(tmp_path)
    with client:
        register_and_login(client)
        response = refresh(client, token)

    assert response.status_code in (401, 422)
    if response.status_code == 401:
        assert response.json() == EXPIRED


def test_expired_refresh_token_is_rejected(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        session = register_and_login(client)
        with app.state.database.engine.begin() as connection:
            connection.execute(update(refresh_tokens).values(
                expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
            ))
        response = refresh(client, session["refresh_token"])

    assert response.status_code == 401
    assert response.json() == EXPIRED


def test_logout_revokes_refresh_token(tmp_path):
    client, _ = make_client(tmp_path)
    with client:
        session = register_and_login(client)
        logout = client.post(
            "/api/v1/users/logout", json={"refresh_token": session["refresh_token"]}
        )
        repeat = client.post(
            "/api/v1/users/logout", json={"refresh_token": session["refresh_token"]}
        )
        response = refresh(client, session["refresh_token"])

    assert logout.status_code == 204
    assert repeat.status_code == 204
    assert response.status_code == 401


def test_logout_only_revokes_that_session(tmp_path):
    client, _ = make_client(tmp_path)
    with client:
        first = register_and_login(client)
        second = client.post(
            "/api/v1/users/login", json={"email": EMAIL, "password": PASSWORD}
        ).json()
        client.post("/api/v1/users/logout", json={"refresh_token": first["refresh_token"]})
        response = refresh(client, second["refresh_token"])

    assert response.status_code == 200


@pytest.mark.parametrize("account_status", ["SUSPENDED", "DISABLED"])
def test_non_active_user_cannot_refresh(tmp_path, account_status):
    client, app = make_client(tmp_path)
    with client:
        session = register_and_login(client)
        app.state.database.update_account_status(EMAIL, account_status)
        response = refresh(client, session["refresh_token"])

    assert response.status_code == 401
    assert response.json() == EXPIRED


def test_admin_suspension_revokes_refresh_tokens(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        admin = register_and_login(client, "admin@u.nus.edu")
        app.state.database.bootstrap_first_admin("admin@u.nus.edu")
        user = register_and_login(client)
        app.state.database.change_account_status(
            admin["user"]["id"], user["user"]["id"], "SUSPENDED", "Testing"
        )
        app.state.database.change_account_status(
            admin["user"]["id"], user["user"]["id"], "ACTIVE", "Reinstated"
        )
        response = refresh(client, user["refresh_token"])

    # Reinstating the account does not revive sessions from before the suspension.
    assert response.status_code == 401
