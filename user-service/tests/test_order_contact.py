import pytest
from test_profile import setup_users, auth


@pytest.mark.parametrize('preference,expected', [('TELEGRAM', '@student'), ('PHONE', '12345678'), ('EMAIL', 'e0000001@u.nus.edu'), (None, None), ('unknown', None)])
def test_internal_contact_requires_service_key_and_returns_only_preference(tmp_path, monkeypatch, preference, expected):
    monkeypatch.setenv('ORDER_CONTACT_SERVICE_KEY', 'contact-only-key')
    client, app, users, token = setup_users(tmp_path)
    try:
        uid = users[0]['id']
        client.patch(f'/api/v1/users/{uid}', headers=auth(token), json={
            'contact_preference': preference, 'telegram_handle': '@student', 'phone_number': '12345678',
        })
        path = f'/api/v1/internal/users/{uid}/contact'
        for headers in ({}, auth(token), {'X-Service-Key': 'wrong'}):
            assert client.get(path, headers=headers).status_code == 403
        response = client.get(path, headers={'X-Service-Key': 'contact-only-key'})
        assert response.status_code == 200
        assert response.json() == {'display_name': 'Student 1', 'contact_preference': preference if expected else None, 'contact': expected}
        monkeypatch.delenv('ORDER_CONTACT_SERVICE_KEY')
        assert client.get(path, headers={'X-Service-Key': 'contact-only-key'}).status_code == 403
    finally:
        client.__exit__(None, None, None)
