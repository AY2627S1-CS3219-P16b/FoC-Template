"""Pydantic schemas for user-service HTTP request and response bodies."""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


NUS_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9]+@u\.nus\.edu$", re.IGNORECASE)


class RegistrationRequest(BaseModel):
    email: str
    password: str
    display_name: str
    contact_preference: str | None = None
    telegram_handle: str | None = None
    phone_number: str | None = None
    profile_picture_url: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not NUS_EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("must be an NUS student email in the format <nusid>@u.nus.edu")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 10:
            raise ValueError("must be at least 10 characters long")
        if not re.search(r"[A-Z]", value):
            raise ValueError("must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("must contain at least one lowercase letter")
        if not re.search(r"\d", value):
            raise ValueError("must contain at least one digit")
        if not re.search(r"[^A-Za-z0-9]", value):
            raise ValueError("must contain at least one symbol")
        return value

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        if len(value) > 100:
            raise ValueError("must not exceed 100 characters")
        return value

    @field_validator(
        "contact_preference",
        "telegram_handle",
        "phone_number",
        "profile_picture_url",
    )
    @classmethod
    def turn_blank_optional_fields_into_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    contact_preference: str | None
    telegram_handle: str | None
    phone_number: str | None
    profile_picture_url: str | None
    auth_role: Literal["USER", "ADMIN"]
    active_role_mode: Literal["REQUESTER", "COURIER"]
    account_status: Literal["ACTIVE", "SUSPENDED", "DISABLED"]
    created_at: datetime


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not NUS_EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("must be an NUS student email in the format <nusid>@u.nus.edu")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value


class AuthenticatedUserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    auth_role: Literal["USER", "ADMIN"]
    active_role_mode: Literal["REQUESTER", "COURIER"]
    account_status: Literal["ACTIVE", "SUSPENDED", "DISABLED"]


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: AuthenticatedUserResponse


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    contact_preference: str | None = None
    telegram_handle: str | None = None
    phone_number: str | None = None
    profile_picture_url: str | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("must not be null")
        return RegistrationRequest.validate_display_name(value)

    @field_validator(
        "contact_preference",
        "telegram_handle",
        "phone_number",
        "profile_picture_url",
    )
    @classmethod
    def normalize_optional_field(cls, value: str | None) -> str | None:
        return RegistrationRequest.turn_blank_optional_fields_into_none(value)

    @model_validator(mode="after")
    def require_a_field(self):
        if not self.model_fields_set:
            raise ValueError("at least one profile field is required")
        return self


class RoleModeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_role_mode: Literal["REQUESTER", "COURIER"]


class AdminChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        if len(value) > 500:
            raise ValueError("must not exceed 500 characters")
        return value


class AuthRoleUpdateRequest(AdminChangeRequest):
    auth_role: Literal["USER", "ADMIN"]


class AccountStatusUpdateRequest(AdminChangeRequest):
    account_status: Literal["ACTIVE", "SUSPENDED", "DISABLED"]


class AdminAuditResponse(BaseModel):
    id: str
    acting_admin_user_id: str
    acting_admin_display_name: str
    acting_admin_email: str
    target_user_id: str
    target_display_name: str
    target_email: str
    action_type: Literal["PROFILE_UPDATED", "AUTH_ROLE_CHANGED", "ACCOUNT_STATUS_CHANGED"]
    previous_value: dict[str, str | None]
    new_value: dict[str, str | None]
    reason: str
    timestamp: datetime


class AdminAuditPageResponse(BaseModel):
    items: list[AdminAuditResponse]
    total: int
    page: int
    page_size: int
