"""Request and response models for the order service endpoints."""

from typing import Annotated, Literal
from datetime import datetime, timedelta
import os

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StringConstraints,
    computed_field, field_validator,
)


OrderStatus = Literal[
    "RESERVING", "OPEN", "ACCEPTED", "PICKED_UP", "DELIVERED",
    "COMPLETING", "COMPLETED", "CANCELLING", "CANCELLED",
    "EXPIRING", "EXPIRED", "REJECTED",
]
OrderRole = Literal["requester", "courier"]
LogOutcome = Literal["SUCCEEDED", "REJECTED", "FAILED"]
RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateOrderRequest(StrictModel):
    """Caller identity and supplier snapshots are supplied by the server."""

    supplier_id: RequiredText = Field(max_length=100)
    item_description: RequiredText
    delivery_location: RequiredText
    credit_amount: int = Field(strict=True, gt=0, le=2147483647)
    expires_at: AwareDatetime
    delivery_instructions: str | None = None

    @field_validator("delivery_instructions")
    @classmethod
    def normalize_instructions(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class OrderResponse(BaseModel):
    id: str
    requester_user_id: str
    courier_user_id: str | None = None
    supplier_id: str
    supplier_name: str
    pickup_location: str
    item_description: str
    delivery_location: str
    delivery_instructions: str | None = None
    credit_amount: int = Field(gt=0, le=2147483647)
    status: OrderStatus
    credit_error: str | None = None
    expires_at: AwareDatetime
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @computed_field
    @property
    def receipt_confirmation_deadline(self) -> datetime | None:
        if self.status != "DELIVERED":
            return None
        return self.updated_at + timedelta(hours=float(os.getenv("AUTO_CONFIRM_RECEIPT_HOURS", "24")))


class PageResponse(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class OrderPageResponse(PageResponse):
    items: list[OrderResponse]


class OrderHistoryEntryResponse(BaseModel):
    id: str
    order_id: str
    actor_user_id: str | None = None
    action: str
    outcome: LogOutcome
    previous_status: OrderStatus | None = None
    new_status: OrderStatus | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: AwareDatetime


class OrderHistoryPageResponse(PageResponse):
    items: list[OrderHistoryEntryResponse]


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ContactResponse(BaseModel):
    display_name: RequiredText
    contact_preference: Literal["TELEGRAM", "PHONE", "EMAIL"] | None = None
    contact: RequiredText | None = None
