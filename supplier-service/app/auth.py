"""Validate supplier callers through the existing User Service profile API."""

import base64
import binascii
import json
from uuid import UUID
from urllib.parse import quote

import httpx
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ValidationError
from typing import Literal

bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: str
    auth_role: Literal["USER", "ADMIN"]
    active_role_mode: Literal["REQUESTER", "COURIER"]
    account_status: Literal["ACTIVE", "SUSPENDED", "DISABLED"]


def unauthorized():
    return HTTPException(401, "Please log in with an active account.",
                         headers={"WWW-Authenticate": "Bearer"})


def current_user(request: Request,
                 credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    if credentials is None:
        raise unauthorized()
    token = credentials.credentials
    try:
        if len(token) > 16384 or len(token.split(".")) != 3:
            raise ValueError("Malformed token")
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > 200:
            raise ValueError("Invalid subject")
        UUID(subject)  # User Service IDs are UUIDs; reject path-like lookup input.
    except (ValueError, TypeError, AttributeError, UnicodeError, binascii.Error):
        raise unauthorized() from None

    # Unverified sub is ONLY a lookup hint. Never trust token role/status claims.
    # User Service verifies the original token's signature and expiry, then reads
    # the current user from its database before returning this profile.
    try:
        response = request.app.state.user_client.get(
            "/api/v1/users/" + quote(subject, safe=""),
            headers={"Authorization": f"Bearer {token}"},
        )
    except httpx.RequestError:
        raise HTTPException(503, "Sign-in verification is temporarily unavailable. Please try again.") from None
    if response.status_code in (401, 403, 404):
        raise unauthorized()
    if response.status_code != 200:
        raise HTTPException(503, "Sign-in verification is temporarily unavailable. Please try again.")
    try:
        user = CurrentUser.model_validate(response.json())
    except (ValueError, ValidationError):
        raise HTTPException(503, "Sign-in verification is temporarily unavailable. Please try again.") from None
    if user.id != subject or user.account_status != "ACTIVE":
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
