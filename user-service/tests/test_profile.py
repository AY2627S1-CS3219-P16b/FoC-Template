from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


SECRET = "test-signing-secret"


def setup_users(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'users.db'}", jwt_secret=SECRET)
    client = TestClient(app)
    client.__enter__()
    users = []
    for number in (1, 2):
        response = client.post('/api/v1/users/register', json={
            'email': f'e000000{number}@u.nus.edu',
            'password': 'StrongPass1!',
            'display_name': f'Student {number}',
        })
        assert response.status_code == 201
        users.append(response.json())
    login = client.post('/api/v1/users/login', json={
        'email': 'e0000001@u.nus.edu', 'password': 'StrongPass1!',
    })
    assert login.status_code == 200
    return client, app, users, login.json()['access_token']


def auth(token):
    return {'Authorization': f'Bearer {token}'}


def test_retrieve_and_update_only_profile_fields(tmp_path):
    client, app, users, token = setup_users(tmp_path)
    try:
        fetched = client.get(f"/api/v1/users/{users[0]['id']}", headers=auth(token))
        assert fetched.status_code == 200
        assert fetched.json()['id'] == users[0]['id']
        assert fetched.json()['active_role_mode'] == 'REQUESTER'
        assert 'password_hash' not in fetched.json()

        response = client.patch(f"/api/v1/users/{users[0]['id']}", headers=auth(token), json={
            'display_name': '  New Name  ',
            'contact_preference': 'EMAIL',
            'telegram_handle': '  @new  ',
            'phone_number': '',
            'profile_picture_url': ' https://example.com/photo.png ',
        })
        assert response.status_code == 200
        assert response.json()['display_name'] == 'New Name'
        assert response.json()['telegram_handle'] == '@new'
        assert response.json()['phone_number'] is None
        assert response.json()['profile_picture_url'] == 'https://example.com/photo.png'
        assert client.get(f"/api/v1/users/{users[0]['id']}", headers=auth(token)).json() == response.json()
        assert app.state.database.find_user_by_email(users[0]['email'])['auth_role'] == 'USER'
    finally:
        client.__exit__(None, None, None)


@pytest.mark.parametrize('changes', [
    {'email': 'e0000002@u.nus.edu'},
    {'auth_role': 'ADMIN'},
    {'active_role_mode': 'COURIER'},
    {'account_status': 'DISABLED'},
    {'display_name': '   '},
    {'display_name': None},
    {},
])
def test_rejects_invalid_or_protected_changes(tmp_path, changes):
    client, app, users, token = setup_users(tmp_path)
    try:
        response = client.patch(f"/api/v1/users/{users[0]['id']}", headers=auth(token), json=changes)
        assert response.status_code == 422
        assert client.get(f"/api/v1/users/{users[0]['id']}", headers=auth(token)).json()['display_name'] == 'Student 1'
    finally:
        client.__exit__(None, None, None)


@pytest.mark.parametrize('token', [None, 'malformed', 'wrong-key', 'expired'])
def test_rejects_invalid_tokens(tmp_path, token):
    client, app, users, valid_token = setup_users(tmp_path)
    try:
        if token == 'wrong-key':
            token = jwt.encode({'sub': users[0]['id'], 'exp': datetime.now(timezone.utc) + timedelta(minutes=5)}, 'wrong', algorithm='HS256')
        elif token == 'expired':
            token = jwt.encode({'sub': users[0]['id'], 'exp': datetime.now(timezone.utc) - timedelta(minutes=1)}, SECRET, algorithm='HS256')
        headers = auth(token) if token else {}
        assert client.patch(f"/api/v1/users/{users[0]['id']}", headers=headers, json={'display_name': 'Changed'}).status_code == 401
        assert client.get(f"/api/v1/users/{users[0]['id']}", headers=headers).status_code == 401
        assert app.state.database.find_user_profile(users[0]['id'])['display_name'] == 'Student 1'
    finally:
        client.__exit__(None, None, None)


def test_non_admin_cannot_change_another_account(tmp_path):
    client, app, users, token = setup_users(tmp_path)
    try:
        url = f"/api/v1/users/{users[1]['id']}"
        assert client.get(url, headers=auth(token)).status_code == 403
        assert client.patch(url, headers=auth(token), json={'display_name': 'Changed'}).status_code == 403
        assert app.state.database.find_user_profile(users[1]['id'])['display_name'] == 'Student 2'
    finally:
        client.__exit__(None, None, None)
