"""Authentication checks independent of the unfinished Order Service app.

AI Assistance Disclosure:
Tool: OpenAI Codex, date: 2026-10-16.
Scope: Generated authentication and authorization tests.
Author review: Pending team review.
"""

import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import current_user, load_jwt_public_key, require_admin


class OrderAuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_pem = cls.private_key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo,
        )

    def setUp(self):
        app = FastAPI()
        app.state.jwt_public_key = self.private_key.public_key()

        @app.get("/identity")
        def identity(user=Depends(current_user)):
            return user

        @app.get("/admin")
        def admin(user=Depends(require_admin)):
            return user

        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def claims(self, **changes):
        return {
            "sub": "student-1", "auth_role": "USER", "active_role_mode": "REQUESTER",
            "account_status": "ACTIVE", "exp": int(time.time()) + 900, **changes,
        }

    def headers(self, claims=None, key=None, algorithm="RS256"):
        token = jwt.encode(
            self.claims() if claims is None else claims,
            self.private_key if key is None else key, algorithm=algorithm,
        )
        return {"Authorization": f"Bearer {token}"}

    def test_valid_identity_in_both_modes(self):
        for mode in ("REQUESTER", "COURIER"):
            response = self.client.get(
                "/identity", headers=self.headers(self.claims(active_role_mode=mode, id="spoofed")),
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["id"], "student-1")
            self.assertEqual(response.json()["active_role_mode"], mode)

    def test_missing_or_malformed_bearer_credentials(self):
        for headers in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer invalid"}):
            response = self.client.get("/identity", headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_wrong_signature_expiry_and_algorithm(self):
        cases = (
            self.headers(key=self.other_key),
            self.headers(self.claims(exp=int(time.time()) - 60)),
            self.headers(key="untrusted-secret", algorithm="HS256"),
        )
        for headers in cases:
            self.assertEqual(self.client.get("/identity", headers=headers).status_code, 401)

    def test_missing_or_invalid_claims(self):
        for field in ("sub", "exp", "auth_role", "active_role_mode", "account_status"):
            claims = self.claims()
            del claims[field]
            self.assertEqual(
                self.client.get("/identity", headers=self.headers(claims)).status_code, 401, field,
            )
        for changes in (
            {"sub": None}, {"auth_role": "OWNER"}, {"active_role_mode": "OTHER"},
            {"account_status": "SUSPENDED"}, {"account_status": "DISABLED"},
        ):
            self.assertEqual(self.client.get(
                "/identity", headers=self.headers(self.claims(**changes)),
            ).status_code, 401)

    def test_admin_guard(self):
        self.assertEqual(self.client.get("/admin").status_code, 401)
        self.assertEqual(self.client.get("/admin", headers=self.headers()).status_code, 403)
        response = self.client.get("/admin", headers=self.headers(self.claims(auth_role="ADMIN")))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["auth_role"], "ADMIN")

    def test_inline_public_key_takes_precedence(self):
        with patch.dict(os.environ, {
            "JWT_PUBLIC_KEY": self.public_pem.decode(), "JWT_PUBLIC_KEY_PATH": "/missing/key.pem",
        }, clear=True):
            key = load_jwt_public_key()
        self.assertEqual(key.public_numbers(), self.private_key.public_key().public_numbers())

    def test_public_key_loaded_from_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "public.pem"
            path.write_bytes(self.public_pem)
            with patch.dict(os.environ, {"JWT_PUBLIC_KEY_PATH": str(path)}, clear=True):
                key = load_jwt_public_key()
        self.assertEqual(key.public_numbers(), self.private_key.public_key().public_numbers())

    def test_missing_or_invalid_public_key_configuration(self):
        for settings in ({}, {"JWT_PUBLIC_KEY": "invalid"}, {"JWT_PUBLIC_KEY_PATH": "/missing/key.pem"}):
            with patch.dict(os.environ, settings, clear=True), self.assertRaises(RuntimeError):
                load_jwt_public_key()
