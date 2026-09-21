from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.database import AdminPermissionError, BootstrapUnavailableError, Database, LastActiveAdminError
from app.main import create_app


PASSWORD = "StrongPass1!"
SECRET = "test-signing-secret"


def register(client, number):
    response = client.post("/api/v1/users/register", json={
        "email": f"e000000{number}@u.nus.edu",
        "password": PASSWORD,
        "display_name": f"Student {number}",
    })
    assert response.status_code == 201
    return response.json()


def token(client, user):
    response = client.post("/api/v1/users/login", json={
        "email": user["email"], "password": PASSWORD,
    })
    assert response.status_code == 200
    return response.json()["access_token"]


def headers(access_token, reason=None):
    result = {"Authorization": f"Bearer {access_token}"}
    if reason is not None:
        result["X-Admin-Reason"] = reason
    return result


@pytest.fixture
def accounts(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'users.db'}", jwt_secret=SECRET)
    with TestClient(app) as client:
        admin = register(client, 1)
        other = register(client, 2)
        third = register(client, 3)
        assert admin["auth_role"] == "USER"
        promoted = app.state.database.bootstrap_first_admin(admin["email"])
        assert promoted.created
        assert promoted.user["auth_role"] == "ADMIN"
        yield client, app, admin, other, third, token(client, admin), token(client, other)


def test_bootstrap_is_idempotent_and_requires_active_registered_account(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'users.db'}", jwt_secret=SECRET)
    with TestClient(app) as client:
        first = register(client, 1)
        second = register(client, 2)
        with pytest.raises(BootstrapUnavailableError):
            app.state.database.bootstrap_first_admin("missing@u.nus.edu")
        app.state.database.update_account_status(second["email"], "SUSPENDED")
        with pytest.raises(BootstrapUnavailableError):
            app.state.database.bootstrap_first_admin(second["email"])
        created = app.state.database.bootstrap_first_admin(first["email"])
        repeated = app.state.database.bootstrap_first_admin(first["email"])
        assert created.created
        assert not repeated.created
        assert repeated.user["id"] == first["id"]
        with pytest.raises(BootstrapUnavailableError):
            app.state.database.bootstrap_first_admin(second["email"])
        assert app.state.database.find_user_profile(second["id"])["auth_role"] == "USER"


def test_bootstrap_command_promotes_existing_account_once(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'users.db'}"
    app = create_app(database_url, jwt_secret=SECRET)
    with TestClient(app) as client:
        user = register(client, 1)

    env_file = tmp_path / "bootstrap.env"
    env_file.write_text(f"DATABASE_URL={database_url}\n")
    environment = {key: value for key, value in os.environ.items() if key != "DATABASE_URL"}
    command = [
        sys.executable, "-m", "app.bootstrap_admin",
        "--env-file", str(env_file), user["email"],
    ]
    first = subprocess.run(command, env=environment, capture_output=True, text=True)
    second = subprocess.run(command, env=environment, capture_output=True, text=True)

    assert first.returncode == 0
    assert user["email"] in first.stdout
    assert second.returncode == 0
    assert "already completed" in second.stdout
    assert app.state.database.find_user_profile(user["id"])["auth_role"] == "ADMIN"


def test_bootstrap_does_not_restore_revoked_privileges_or_status(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'users.db'}", jwt_secret=SECRET)
    with TestClient(app) as client:
        first = register(client, 1)
        second = register(client, 2)
        original_hash = app.state.database.find_user_by_email(first["email"])["password_hash"]
        assert app.state.database.bootstrap_first_admin(first["email"]).created
        app.state.database.change_auth_role(first["id"], second["id"], "ADMIN", "Backup admin")
        app.state.database.change_auth_role(second["id"], first["id"], "USER", "Privilege revoked")
        app.state.database.change_account_status(second["id"], first["id"], "DISABLED", "Account closed")

        repeated = app.state.database.bootstrap_first_admin(first["email"])
        assert not repeated.created
        assert repeated.user["auth_role"] == "USER"
        assert repeated.user["account_status"] == "DISABLED"
        assert app.state.database.find_user_by_email(first["email"])["password_hash"] == original_hash


def test_concurrent_bootstrap_for_same_account_is_harmless(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'users.db'}"
    app = create_app(database_url, jwt_secret=SECRET)
    with TestClient(app) as client:
        user = register(client, 1)
        barrier = Barrier(2)

        def bootstrap():
            barrier.wait()
            database = Database(database_url)
            try:
                return database.bootstrap_first_admin(user["email"])
            finally:
                database.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: bootstrap(), range(2)))

        assert sorted(result.created for result in results) == [False, True]
        assert {result.user["id"] for result in results} == {user["id"]}
        assert app.state.database.find_user_profile(user["id"])["auth_role"] == "ADMIN"


def test_concurrent_bootstrap_for_different_accounts_has_one_winner(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'users.db'}"
    app = create_app(database_url, jwt_secret=SECRET)
    with TestClient(app) as client:
        first = register(client, 1)
        second = register(client, 2)
        barrier = Barrier(2)

        def bootstrap(email):
            barrier.wait()
            database = Database(database_url)
            try:
                return database.bootstrap_first_admin(email).created
            except BootstrapUnavailableError:
                return False
            finally:
                database.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_result = executor.submit(bootstrap, first["email"])
            second_result = executor.submit(bootstrap, second["email"])
            assert sorted([first_result.result(), second_result.result()]) == [False, True]

        admins = [
            user for user in app.state.database.list_user_profiles()
            if user["auth_role"] == "ADMIN"
        ]
        assert len(admins) == 1


def test_admin_can_list_view_and_edit_another_profile_with_audit(accounts):
    client, app, admin, other, third, admin_token, user_token = accounts
    listing = client.get("/api/v1/users", headers=headers(admin_token))
    assert listing.status_code == 200
    assert {item["id"] for item in listing.json()} == {admin["id"], other["id"], third["id"]}
    assert all("password_hash" not in item for item in listing.json())
    assert client.get(f"/api/v1/users/{other['id']}", headers=headers(admin_token)).status_code == 200
    assert client.get("/api/v1/users/missing", headers=headers(admin_token)).status_code == 404

    response = client.patch(
        f"/api/v1/users/{other['id']}",
        headers=headers(admin_token, " Correct display name "),
        json={"display_name": "  New Name  ", "telegram_handle": " @new "},
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "New Name"
    assert response.json()["telegram_handle"] == "@new"
    assert app.state.database.find_user_profile(other["id"])["display_name"] == "New Name"
    audit_page = client.get("/api/v1/admin/audit-logs", headers=headers(admin_token)).json()
    audit = audit_page["items"]
    assert audit_page["total"] == 1
    assert len(audit) == 1
    assert audit[0]["acting_admin_user_id"] == admin["id"]
    assert audit[0]["target_user_id"] == other["id"]
    assert audit[0]["action_type"] == "PROFILE_UPDATED"
    assert audit[0]["previous_value"] == {"display_name": "Student 2", "telegram_handle": None}
    assert audit[0]["new_value"] == {"display_name": "New Name", "telegram_handle": "@new"}
    assert audit[0]["reason"] == "Correct display name"
    assert audit[0]["acting_admin_display_name"] == admin["display_name"]
    assert audit[0]["acting_admin_email"] == admin["email"]
    assert audit[0]["target_display_name"] == "New Name"
    assert audit[0]["target_email"] == other["email"]
    assert datetime.fromisoformat(audit[0]["timestamp"])

    repeated = client.patch(
        f"/api/v1/users/{other['id']}", headers=headers(admin_token, "No change"),
        json={"display_name": "New Name"},
    )
    assert repeated.status_code == 200
    assert len(app.state.database.list_admin_audit_logs()) == 1


@pytest.mark.parametrize("invalid_headers,body", [
    ({}, {"display_name": "Changed"}),
    ({"X-Admin-Reason": "   "}, {"display_name": "Changed"}),
    ({"X-Admin-Reason": "reason"}, {"auth_role": "ADMIN"}),
    ({"X-Admin-Reason": "reason"}, {"display_name": "   "}),
])
def test_admin_profile_update_requires_reason_and_same_validation(accounts, invalid_headers, body):
    client, app, admin, other, _, admin_token, _ = accounts
    request_headers = headers(admin_token)
    request_headers.update(invalid_headers)
    response = client.patch(f"/api/v1/users/{other['id']}", headers=request_headers, json=body)
    assert response.status_code == 422
    assert app.state.database.find_user_profile(other["id"])["display_name"] == "Student 2"
    assert app.state.database.list_admin_audit_logs() == []


def test_admin_can_promote_and_demote_another_account(accounts):
    client, app, admin, other, _, admin_token, user_token = accounts
    url = f"/api/v1/users/{other['id']}/auth-role"
    promoted = client.patch(url, headers=headers(admin_token), json={
        "auth_role": "ADMIN", "reason": "Volunteer moderator",
    })
    assert promoted.status_code == 200
    assert promoted.json()["auth_role"] == "ADMIN"
    assert client.get("/api/v1/users", headers=headers(user_token)).status_code == 200

    demoted = client.patch(url, headers=headers(admin_token), json={
        "auth_role": "USER", "reason": "Term ended",
    })
    assert demoted.status_code == 200
    assert demoted.json()["auth_role"] == "USER"
    assert client.get("/api/v1/users", headers=headers(user_token)).status_code == 403
    audit = app.state.database.list_admin_audit_logs()
    assert [item["action_type"] for item in audit] == ["AUTH_ROLE_CHANGED", "AUTH_ROLE_CHANGED"]
    assert audit[0]["previous_value"] == {"auth_role": "USER"}
    assert audit[0]["new_value"] == {"auth_role": "ADMIN"}
    assert audit[1]["previous_value"] == {"auth_role": "ADMIN"}
    assert audit[1]["new_value"] == {"auth_role": "USER"}

    first_page = client.get(
        "/api/v1/admin/audit-logs?page=1&page_size=1", headers=headers(admin_token)
    ).json()
    second_page = client.get(
        "/api/v1/admin/audit-logs?page=2&page_size=1", headers=headers(admin_token)
    ).json()
    assert first_page["total"] == second_page["total"] == 2
    assert first_page["items"][0]["new_value"] == {"auth_role": "USER"}
    assert second_page["items"][0]["new_value"] == {"auth_role": "ADMIN"}
    assert client.get(
        "/api/v1/admin/audit-logs?page=3&page_size=1", headers=headers(admin_token)
    ).json()["items"] == []


def test_non_admin_cannot_manage_other_accounts(accounts):
    client, app, admin, other, _, admin_token, user_token = accounts
    assert client.get("/api/v1/users", headers=headers(user_token)).status_code == 403
    assert client.get("/api/v1/admin/audit-logs", headers=headers(user_token)).status_code == 403
    assert client.get(f"/api/v1/users/{admin['id']}", headers=headers(user_token)).status_code == 403
    assert client.patch(
        f"/api/v1/users/{admin['id']}", headers=headers(user_token, "try"),
        json={"display_name": "Changed"},
    ).status_code == 403
    assert client.patch(
        f"/api/v1/users/{admin['id']}/auth-role", headers=headers(user_token),
        json={"auth_role": "USER", "reason": "try"},
    ).status_code == 403
    assert client.patch(
        f"/api/v1/users/{admin['id']}/status", headers=headers(user_token),
        json={"account_status": "SUSPENDED", "reason": "try"},
    ).status_code == 403
    assert app.state.database.find_user_profile(admin["id"])["auth_role"] == "ADMIN"
    assert app.state.database.list_admin_audit_logs() == []


def test_admin_cannot_demote_or_disable_self_but_can_use_regular_actions(accounts):
    client, app, admin, _, _, admin_token, _ = accounts
    assert client.patch(
        f"/api/v1/users/{admin['id']}/auth-role", headers=headers(admin_token),
        json={"auth_role": "USER", "reason": "self"},
    ).status_code == 403
    assert client.patch(
        f"/api/v1/users/{admin['id']}/status", headers=headers(admin_token),
        json={"account_status": "DISABLED", "reason": "self"},
    ).status_code == 403
    own_profile = client.patch(
        f"/api/v1/users/{admin['id']}", headers=headers(admin_token),
        json={"display_name": "Admin Name"},
    )
    assert own_profile.status_code == 200
    assert own_profile.json()["display_name"] == "Admin Name"
    switched = client.patch(
        f"/api/v1/users/{admin['id']}/role-mode", headers=headers(admin_token),
        json={"active_role_mode": "COURIER"},
    )
    assert switched.status_code == 200
    assert switched.json()["active_role_mode"] == "COURIER"
    assert app.state.database.list_admin_audit_logs() == []


def test_admin_status_changes_are_audited_and_inactive_admin_loses_access(accounts):
    client, app, admin, other, _, admin_token, user_token = accounts
    promote = client.patch(f"/api/v1/users/{other['id']}/auth-role", headers=headers(admin_token), json={
        "auth_role": "ADMIN", "reason": "coverage",
    })
    assert promote.status_code == 200
    suspend = client.patch(f"/api/v1/users/{other['id']}/status", headers=headers(admin_token), json={
        "account_status": "SUSPENDED", "reason": "Policy violation",
    })
    assert suspend.status_code == 200
    assert suspend.json()["account_status"] == "SUSPENDED"
    assert client.get("/api/v1/users", headers=headers(user_token)).status_code == 401
    last_audit = app.state.database.list_admin_audit_logs()[-1]
    assert last_audit["action_type"] == "ACCOUNT_STATUS_CHANGED"
    assert last_audit["previous_value"] == {"account_status": "ACTIVE"}
    assert last_audit["new_value"] == {"account_status": "SUSPENDED"}
    assert last_audit["reason"] == "Policy violation"


def test_invalid_role_status_and_noop_are_rejected_without_audit(accounts):
    client, app, admin, other, _, admin_token, _ = accounts
    role_url = f"/api/v1/users/{other['id']}/auth-role"
    status_url = f"/api/v1/users/{other['id']}/status"
    assert client.patch(role_url, headers=headers(admin_token), json={"auth_role": "ADMIN"}).status_code == 422
    assert client.patch(role_url, headers=headers(admin_token), json={"auth_role": "OWNER", "reason": "x"}).status_code == 422
    assert client.patch(role_url, headers=headers(admin_token), json={"auth_role": "USER", "reason": "x"}).status_code == 409
    assert client.patch(status_url, headers=headers(admin_token), json={"account_status": "BANNED", "reason": "x"}).status_code == 422
    assert client.patch(status_url, headers=headers(admin_token), json={"account_status": "ACTIVE", "reason": "x"}).status_code == 409
    assert app.state.database.list_admin_audit_logs() == []


def test_simultaneous_admin_deactivations_leave_one_active_admin(accounts):
    client, app, admin, other, _, admin_token, _ = accounts
    promoted = client.patch(
        f"/api/v1/users/{other['id']}/auth-role",
        headers=headers(admin_token),
        json={"auth_role": "ADMIN", "reason": "Shared coverage"},
    )
    assert promoted.status_code == 200
    barrier = Barrier(2)

    def deactivate(actor_id, target_id):
        barrier.wait()
        try:
            app.state.database.change_account_status(
                actor_id, target_id, "SUSPENDED", "Concurrent test"
            )
            return "changed"
        except (AdminPermissionError, LastActiveAdminError):
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(deactivate, admin["id"], other["id"])
        second = executor.submit(deactivate, other["id"], admin["id"])
        results = [first.result(), second.result()]

    assert sorted(results) == ["blocked", "changed"]
    active_admins = [
        user for user in app.state.database.list_user_profiles()
        if user["auth_role"] == "ADMIN" and user["account_status"] == "ACTIVE"
    ]
    assert len(active_admins) == 1
