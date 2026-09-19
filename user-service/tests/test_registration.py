import pytest

from fastapi.testclient import TestClient

from app.main import create_app


def make_client(tmp_path):
    app = create_app(
        f"sqlite:///{tmp_path / 'users.db'}", jwt_secret="test-signing-secret"
    )
    return TestClient(app), app


def valid_registration(**overrides):
    payload = {
        "email": "e0123456@u.nus.edu",
        "password": "StrongPass1!",
        "display_name": "NUS Student",
    }
    payload.update(overrides)
    return payload


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        create_app()


def test_jwt_secret_is_required(tmp_path, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="JWT_SECRET is required"):
        create_app(f"sqlite:///{tmp_path / 'users.db'}")


def test_cors_origins_are_required(tmp_path, monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS")

    with pytest.raises(RuntimeError, match="CORS_ORIGINS is required"):
        create_app(
            f"sqlite:///{tmp_path / 'users.db'}", jwt_secret="test-signing-secret"
        )


def test_registers_user_with_defaults_and_no_optional_fields(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        response = client.post("/api/v1/users/register", json=valid_registration())

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "e0123456@u.nus.edu"
    assert body["auth_role"] == "USER"
    assert body["active_role_mode"] == "REQUESTER"
    assert body["account_status"] == "ACTIVE"
    assert body["telegram_handle"] is None
    assert "password" not in body

    password_hash = app.state.database.find_user_by_email(
        "e0123456@u.nus.edu"
    )["password_hash"]
    assert password_hash != "StrongPass1!"
    assert password_hash.startswith("$argon2")


@pytest.mark.parametrize("account_status", ["ACTIVE", "SUSPENDED", "DISABLED"])
def test_rejects_duplicate_email_case_insensitively_for_any_status(
    tmp_path, account_status
):
    client, app = make_client(tmp_path)
    with client:
        assert client.post(
            "/api/v1/users/register", json=valid_registration()
        ).status_code == 201
        app.state.database.update_account_status(
            "e0123456@u.nus.edu", account_status
        )
        response = client.post(
            "/api/v1/users/register",
            json=valid_registration(email="E0123456@u.nus.edu"),
        )

    assert response.status_code == 409
    assert response.json()["errors"][0]["field"] == "email"


def test_rejects_non_nus_email_without_creating_user(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        response = client.post(
            "/api/v1/users/register",
            json=valid_registration(email="student@gmail.com"),
        )

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "email"
    assert app.state.database.count_users() == 0


def test_rejects_each_invalid_password_rule(tmp_path):
    invalid_passwords = [
        "Short1!",
        "lowercase1!",
        "UPPERCASE1!",
        "NoDigitsHere!",
        "NoSymbols123",
    ]
    client, _ = make_client(tmp_path)
    with client:
        for password in invalid_passwords:
            response = client.post(
                "/api/v1/users/register",
                json=valid_registration(password=password),
            )
            assert response.status_code == 422
            assert response.json()["errors"][0]["field"] == "password"


def test_identifies_missing_required_fields(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        response = client.post("/api/v1/users/register", json={})

    assert response.status_code == 422
    assert {error["field"] for error in response.json()["errors"]} == {
        "email",
        "password",
        "display_name",
    }
    assert app.state.database.count_users() == 0
