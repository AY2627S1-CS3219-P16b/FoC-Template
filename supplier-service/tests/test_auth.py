import base64
import json
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
from fastapi import Depends
from fastapi.testclient import TestClient

from app.auth import current_user
from app.main import create_app


class SupplierAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.user_id = str(uuid4())
        self.profile = dict(id=self.user_id, auth_role="USER",
                            active_role_mode="REQUESTER", account_status="ACTIVE")
        self.upstream_status = 200
        self.upstream_body = None
        self.unavailable = False
        self.requests = []
        def user_service(request):
            self.requests.append(request)
            if self.unavailable:
                raise httpx.ConnectError("unreachable", request=request)
            return httpx.Response(self.upstream_status,
                                  json=self.profile if self.upstream_body is None else self.upstream_body)
        self.engine = MagicMock()
        with patch("app.main.create_database_engine", return_value=self.engine):
            self.app = create_app()
        self.upstream = httpx.Client(base_url="http://user-service", transport=httpx.MockTransport(user_service))
        self.app.state.user_client = self.upstream
        self.app.state.database = self.engine
        self.client = TestClient(self.app)
        self.paths = ["/api/v1/places", "/api/v1/suppliers", f"/api/v1/suppliers/{uuid4()}"]

    def tearDown(self):
        self.client.close()
        self.upstream.close()

    def token(self, **claims):
        payload = {"sub": self.user_id, "auth_role": "ADMIN", **claims}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        # Signature acceptance is controlled by the mocked User Service, not local decode.
        return f"header.{encoded}.signature"

    def headers(self, **claims):
        return {"Authorization": "Bearer " + self.token(**claims)}

    def test_missing_and_malformed_credentials_rejected_before_database(self):
        for path in self.paths:
            for headers in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer garbage"},
                            self.headers(sub=None), self.headers(sub="../admin")):
                response = self.client.get(path, headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
        self.assertEqual(self.requests, [])
        self.engine.connect.assert_not_called()

    def test_upstream_rejections_reject_all_endpoints(self):
        for code in (401, 403, 404):
            self.upstream_status = code
            for path in self.paths:
                self.assertEqual(self.client.get(path, headers=self.headers()).status_code, 401)
        self.engine.connect.assert_not_called()

    def test_active_user_can_browse_and_current_profile_is_authoritative(self):
        with patch("app.main.list_places", return_value=[]), patch("app.main.count_suppliers", return_value=0), \
                patch("app.main.list_suppliers", return_value=[]), patch("app.main.get_supplier", return_value=None):
            for role in ("USER", "ADMIN"):
                for mode in ("REQUESTER", "COURIER"):
                    self.profile.update(auth_role=role, active_role_mode=mode)
                    self.assertEqual(self.client.get(self.paths[0], headers=self.headers()).status_code, 200)
                    self.assertEqual(self.client.get(self.paths[1], headers=self.headers()).status_code, 200)
            self.assertEqual(self.client.get(self.paths[2], headers=self.headers()).status_code, 404)
        @self.app.get("/test-identity")
        def identity(user=Depends(current_user)):
            return user
        self.profile["auth_role"] = "USER"
        response = self.client.get("/test-identity", headers=self.headers())
        self.assertEqual(response.json()["auth_role"], "USER")  # token says ADMIN
        self.assertEqual(self.requests[-1].headers["Authorization"], self.headers()["Authorization"])
        self.assertEqual(self.requests[-1].url.path, f"/api/v1/users/{self.user_id}")

    def test_inactive_and_mismatched_profiles_rejected(self):
        for account_status in ("SUSPENDED", "DISABLED"):
            self.profile["account_status"] = account_status
            self.assertEqual(self.client.get(self.paths[1], headers=self.headers()).status_code, 401)
        self.profile.update(account_status="ACTIVE", id=str(uuid4()))
        self.assertEqual(self.client.get(self.paths[1], headers=self.headers()).status_code, 401)
        self.engine.connect.assert_not_called()

    def test_unavailable_or_invalid_user_service_fails_closed(self):
        self.unavailable = True
        self.assertEqual(self.client.get(self.paths[1], headers=self.headers()).status_code, 503)
        self.unavailable = False
        for status in (302, 429, 500):
            self.upstream_status = status
            self.assertEqual(self.client.get(self.paths[1], headers=self.headers()).status_code, 503)
        self.upstream_status = 200
        self.upstream_body = {"unexpected": "response"}
        self.assertEqual(self.client.get(self.paths[1], headers=self.headers()).status_code, 503)
        self.engine.connect.assert_not_called()

    def test_openapi_requires_bearer_auth(self):
        for path in ("/api/v1/places", "/api/v1/suppliers", "/api/v1/suppliers/{supplier_id}"):
            self.assertEqual(self.app.openapi()["paths"][path]["get"]["security"], [{"HTTPBearer": []}])
