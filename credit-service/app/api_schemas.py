"""Request and response models for the credit endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ReservationStatus = Literal["RESERVED", "RELEASED", "TRANSFERRED"]
LedgerEntryType = Literal[
    "INITIAL_ALLOCATION",
    "CREDIT_RESERVED",
    "CREDIT_RELEASED",
    "CREDIT_TRANSFERRED_IN",
    "CREDIT_TRANSFERRED_OUT",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def strip_required_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def strip_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


class CreditBalanceResponse(BaseModel):
    user_id: str
    available_balance: int
    reserved_balance: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReservationResponse(BaseModel):
    id: str
    order_id: str
    requester_user_id: str
    courier_user_id: str | None = None
    amount: int = Field(gt=0)
    status: ReservationStatus
    created_at: datetime
    updated_at: datetime


class LedgerEntryResponse(BaseModel):
    id: str
    user_id: str
    order_id: str | None = None
    type: LedgerEntryType
    amount: int
    available_balance_after: int
    reserved_balance_after: int
    reservation_id: str | None = None
    idempotency_key: str | None = None
    created_at: datetime


class LedgerPageResponse(BaseModel):
    items: list[LedgerEntryResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ReserveCreditsRequest(StrictModel):
    order_id: str = Field(max_length=100)
    amount: int = Field(gt=0)
    idempotency_key: str | None = Field(default=None, max_length=200)

    @field_validator("order_id")
    @classmethod
    def validate_order_id(cls, value: str) -> str:
        return strip_required_text(value)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str | None) -> str | None:
        return strip_optional_text(value)


class ReleaseCreditsRequest(StrictModel):
    idempotency_key: str | None = Field(default=None, max_length=200)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str | None) -> str | None:
        return strip_optional_text(value)


class TransferCreditsRequest(StrictModel):
    courier_user_id: str = Field(max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=200)

    @field_validator("courier_user_id")
    @classmethod
    def validate_courier_user_id(cls, value: str) -> str:
        return strip_required_text(value)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str | None) -> str | None:
        return strip_optional_text(value)
