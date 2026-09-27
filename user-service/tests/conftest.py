import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def generate_jwt_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return {
        "private": private_key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        ).decode(),
        "public": private_key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode(),
    }


@pytest.fixture(scope="session")
def jwt_keys():
    return generate_jwt_keys()


@pytest.fixture(scope="session")
def wrong_jwt_keys():
    return generate_jwt_keys()


@pytest.fixture
def jwt_private_key(jwt_keys):
    return jwt_keys["private"]


@pytest.fixture
def jwt_public_key(jwt_keys):
    return jwt_keys["public"]


@pytest.fixture
def wrong_jwt_private_key(wrong_jwt_keys):
    return wrong_jwt_keys["private"]


@pytest.fixture
def wrong_jwt_public_key(wrong_jwt_keys):
    return wrong_jwt_keys["public"]


@pytest.fixture(autouse=True)
def configure_test_environment(monkeypatch, jwt_keys):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("JWT_PRIVATE_KEY", jwt_keys["private"])
    monkeypatch.setenv("JWT_PUBLIC_KEY", jwt_keys["public"])
