"""Validate supplier callers by verifying their token locally.

User Service signs access tokens with RS256 and shares only the public key,
which can verify a signature but never produce one. This service never calls
User Service to authenticate a caller and never sees its private key.
"""

import os
from typing import Literal

from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
import jwt
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ValidationError

bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: str
    auth_role: Literal["USER", "ADMIN"]
    active_role_mode: Literal["REQUESTER", "COURIER"]
    account_status: Literal["ACTIVE", "SUSPENDED", "DISABLED"]


def load_jwt_public_key() -> RSAPublicKey:
    """Read the public half of User Service's signing key.

    Same env var convention as User Service's own key loading: an inline
    value takes precedence, otherwise read the file at *_PATH.
    """
    value = os.getenv("JWT_PUBLIC_KEY")
    if not value:
        path = os.getenv("JWT_PUBLIC_KEY_PATH")
        if not path:
            raise RuntimeError("JWT_PUBLIC_KEY or JWT_PUBLIC_KEY_PATH is required")
        try:
            with open(path, "rb") as key_file:
                value = key_file.read()
        except OSError as error:
            raise RuntimeError(f"Could not read JWT_PUBLIC_KEY_PATH: {path}") from error
    else:
        value = value.encode()

    try:
        key = load_pem_public_key(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError("JWT_PUBLIC_KEY must be a valid PEM-encoded RSA key") from error
    if not isinstance(key, RSAPublicKey):
        raise RuntimeError("JWT_PUBLIC_KEY must be an RSA key")
    return key


def unauthorized():
    return HTTPException(401, "Please log in with an active account.",
                         headers={"WWW-Authenticate": "Bearer"})


def current_user(request: Request,
                 credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    if credentials is None:
        raise unauthorized()
    try:
        claims = jwt.decode(
            credentials.credentials,
            request.app.state.jwt_public_key,
            algorithms=["RS256"],
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWTError:
        raise unauthorized() from None

    try:
        user = CurrentUser.model_validate({**claims, "id": claims.get("sub")})
    except ValidationError:
        raise unauthorized() from None
    if user.account_status != "ACTIVE":
        raise unauthorized()
    return user


def require_admin(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    """Callers allowed to change supplier records.

    403 rather than 401: the caller is known, the role is not sufficient.
    The wording matches User Service so both services deny alike.
    """
    if user.auth_role != "ADMIN":
        raise HTTPException(403, "Admin access is required.")
    return user


def admin_reason(
    x_admin_reason: str = Header(
        ..., alias="X-Admin-Reason", max_length=500,
        description="Why this change is being made; stored in the audit log",
    )
) -> str:
    """The justification an admin must give, recorded with every write."""
    reason = x_admin_reason.strip()
    if not reason:
        raise HTTPException(422, "X-Admin-Reason must contain 1 to 500 characters.")
    return reason
