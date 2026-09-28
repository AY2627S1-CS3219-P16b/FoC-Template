import time
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)
from fastapi import Depends
from fastapi.testclient import TestClient

from app.auth import current_user
from app.main import create_app


class SupplierAuthenticationTests(unittest.TestCase):
    """Tokens are verified locally with the public half of an RS256 keypair.

    A token signed by the matching private key is trusted outright: nothing
    here calls another service, so the only thing to prove is that signature,
    expiry, and claim checks are enforced, and that a token signed by any
    other key is rejected regardless of what it claims.
    """

    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_pem = cls.private_key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        cls.private_pem = cls.private_key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        # A second, unrelated key: signs tokens Supplier Service must reject.
        cls.other_private_pem = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        ).private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

    def setUp(self):
        self.user_id = str(uuid4())
        self.engine = MagicMock()
        with patch("app.main.create_database_engine", return_value=self.engine), \
             patch("app.main.load_jwt_public_key", return_value=self.private_key.public_key()):
            self.app = create_app()
        self.app.state.jwt_public_key = self.private_key.public_key()
        self.app.state.database = self.engine
        self.client = TestClient(self.app)
        self.paths = ["/api/v1/places", "/api/v1/suppliers", f"/api/v1/suppliers/{uuid4()}"]

    def tearDown(self):
        self.client.close()

    def token(self, key=None, expires_in=900, **claims):
        payload = {
            "sub": self.user_id, "auth_role": "USER", "active_role_mode": "REQUESTER",
            "account_status": "ACTIVE", "exp": int(time.time()) + expires_in, **claims,
        }
        return jwt.encode(payload, key or self.private_pem, algorithm="RS256")

    def headers(self, **claims):
        return {"Authorization": f"Bearer {self.token(**claims)}"}

    def test_missing_and_malformed_credentials_rejected_before_database(self):
        for headers in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer garbage"}):
            for path in self.paths:
                response = self.client.get(path, headers=headers)
                self.assertEqual(response.status_code, 401, path)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
        self.engine.connect.assert_not_called()

    def test_valid_token_authenticates_and_claims_pass_through(self):
        with patch("app.main.list_places", return_value=[]), patch("app.main.count_suppliers", return_value=0), \
                patch("app.main.list_suppliers", return_value=[]), patch("app.main.get_supplier", return_value=None):
            for role in ("USER", "ADMIN"):
                for mode in ("REQUESTER", "COURIER"):
                    headers = self.headers(auth_role=role, active_role_mode=mode)
                    self.assertEqual(self.client.get(self.paths[0], headers=headers).status_code, 200)
                    self.assertEqual(self.client.get(self.paths[1], headers=headers).status_code, 200)
            self.assertEqual(self.client.get(self.paths[2], headers=self.headers()).status_code, 404)

        @self.app.get("/test-identity")
        def identity(user=Depends(current_user)):
            return user
        response = self.client.get("/test-identity", headers=self.headers(auth_role="ADMIN"))
        self.assertEqual(response.json()["auth_role"], "ADMIN")
        self.assertEqual(response.json()["id"], self.user_id)

    def test_tampered_or_wrongly_signed_tokens_rejected(self):
        # Flip a character in the middle of the signature, not the last one:
        # base64url's final character can have unused bits, so a flip there
        # occasionally decodes to the same bytes and the signature survives.
        genuine = self.token()
        header, payload, signature = genuine.split(".")
        middle = len(signature) // 2
        flipped_char = "A" if signature[middle] != "A" else "B"
        tampered = f"{header}.{payload}.{signature[:middle]}{flipped_char}{signature[middle + 1:]}"

        cases = [
            tampered,
            self.token(key=self.other_private_pem),  # different key entirely
            self.token(expires_in=-60),               # already expired
        ]
        for token in cases:
            response = self.client.get(self.paths[1], headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(response.status_code, 401, token)
        self.engine.connect.assert_not_called()

    def test_missing_required_claims_rejected(self):
        for claims in ({"sub": None}, {"account_status": "not-a-real-status"}):
            payload = {"sub": self.user_id, "auth_role": "USER", "active_role_mode": "REQUESTER",
                       "account_status": "ACTIVE", "exp": int(time.time()) + 900, **claims}
            token = jwt.encode(payload, self.private_pem, algorithm="RS256")
            response = self.client.get(self.paths[1], headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(response.status_code, 401, claims)
        # A token missing `exp` entirely: our own required-claims check, not just PyJWT's.
        payload = {"sub": self.user_id, "auth_role": "USER", "active_role_mode": "REQUESTER",
                   "account_status": "ACTIVE"}
        token = jwt.encode(payload, self.private_pem, algorithm="RS256")
        self.assertEqual(
            self.client.get(self.paths[1], headers={"Authorization": f"Bearer {token}"}).status_code,
            401,
        )

    def test_inactive_account_status_rejected(self):
        for account_status in ("SUSPENDED", "DISABLED"):
            headers = self.headers(account_status=account_status)
            self.assertEqual(self.client.get(self.paths[1], headers=headers).status_code, 401)
        self.engine.connect.assert_not_called()

    def test_openapi_requires_bearer_auth(self):
        for path in ("/api/v1/places", "/api/v1/suppliers", "/api/v1/suppliers/{supplier_id}"):
            self.assertEqual(self.app.openapi()["paths"][path]["get"]["security"], [{"HTTPBearer": []}])
