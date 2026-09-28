"""Request and response models for the supplier endpoints."""

from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from .classification import normalize_tags, validate_supplier_type


class PlaceSummary(BaseModel):
    """The place a supplier sits in, plus the place containing it."""

    id: UUID
    name: str
    parent_id: UUID | None = None
    parent_name: str | None = None


class PlaceResponse(BaseModel):
    id: UUID
    name: str
    search_key: str
    parent_id: UUID | None = None
    parent_name: str | None = None


class SupplierResponse(BaseModel):
    """One supplier. Lists and the single-supplier endpoint return the same
    fields: at this catalogue size a narrower list model would save under 2KB
    a page and cost every caller a second request for the rest."""

    id: UUID
    name: str
    supplier_type: str
    tags: list[str]
    place: PlaceSummary
    floor: str | None = None
    location_description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    opening_time: time
    closing_time: time
    image_url: str | None = None
    pickup_instructions: str | None = None
    is_active: bool

    @classmethod
    def from_row(cls, row: dict) -> "SupplierResponse":
        """Build from a flat query row, nesting the place columns."""
        return cls(
            place=PlaceSummary(
                id=row["place_id"],
                name=row["place_name"],
                parent_id=row["place_parent_id"],
                parent_name=row["place_parent_name"],
            ),
            **{key: value for key, value in row.items() if not key.startswith("place_")},
        )


class SupplierPage(BaseModel):
    """A page of suppliers plus the totals a pager needs."""

    items: list[SupplierResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


# Lengths mirror the columns so over-long input is refused with 422 rather than
# reaching the database.
class SupplierCreate(BaseModel):
    """A new supplier. Category and tags are checked before any write."""

    name: str = Field(min_length=1, max_length=200)
    supplier_type: str
    place_id: UUID
    tags: list[str] = Field(default_factory=list)
    # Required: 00:00 to 23:59 means open around the clock, and a closing time
    # before the opening time means trading past midnight.
    opening_time: time
    closing_time: time
    floor: str | None = Field(default=None, max_length=30)
    location_description: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    image_url: str | None = None
    pickup_instructions: str | None = None
    is_active: bool = True

    @field_validator("name", "floor", "location_description", "image_url",
                     "pickup_instructions")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str:
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("floor")
    @classmethod
    def floor_is_a_label_not_a_sentence(cls, value: str | None) -> str | None:
        # A short code such as B1, G or 13, not free text like "Level 1".
        if value is not None and not value.isalnum():
            raise ValueError("floor must contain only letters and digits, e.g. B1, G, 13")
        return value

    @field_validator("supplier_type")
    @classmethod
    def known_category(cls, value: str) -> str:
        return validate_supplier_type(value)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)


class SupplierUpdate(SupplierCreate):
    """Fields to change. Anything omitted is left alone.

    Every field is optional, but the ones the database requires cannot be set
    to null, so sending `"name": null` is refused rather than writing a blank.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    supplier_type: str | None = None
    place_id: UUID | None = None
    tags: list[str] | None = None
    opening_time: time | None = None
    closing_time: time | None = None
    is_active: bool | None = None

    @field_validator("supplier_type")
    @classmethod
    def known_category(cls, value: str | None) -> str | None:
        return None if value is None else validate_supplier_type(value)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else normalize_tags(value)

    @model_validator(mode="after")
    def required_fields_keep_a_value(self) -> "SupplierUpdate":
        required = ("name", "supplier_type", "place_id", "tags", "is_active",
                    "opening_time", "closing_time")
        cleared = [
            field for field in required
            if field in self.model_fields_set and getattr(self, field) is None
        ]
        if cleared:
            raise ValueError(f"{', '.join(cleared)} cannot be set to null")
        if not self.model_fields_set:
            raise ValueError("supply at least one field to change")
        return self


class AuditLogResponse(BaseModel):
    """One recorded admin change."""

    id: UUID
    acting_admin_user_id: UUID
    entity_type: str
    entity_id: UUID
    action_type: str
    previous_value: dict
    new_value: dict
    reason: str | None = None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class PlaceCreate(BaseModel):
    """A new place, optionally inside an existing one."""

    name: str = Field(min_length=1, max_length=200)
    parent_id: UUID | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped
