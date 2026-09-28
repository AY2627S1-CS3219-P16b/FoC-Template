"""Supplier records owned by the Supplier Service."""

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, MetaData,
    String, Table, Text, Time, UniqueConstraint, Uuid, func, text, true,
)
from sqlalchemy.dialects.postgresql import JSONB
from uuid import uuid4

from .places import place_key_default
from .classification import MAX_TAGS, SUPPLIER_TYPES, SupplierTags

metadata = MetaData()

places = Table(
    "places",
    metadata,
    Column("id", Uuid, primary_key=True, default=uuid4),
    Column("parent_id", Uuid, ForeignKey("places.id", ondelete="RESTRICT")),
    CheckConstraint("id <> parent_id", name="place_not_own_parent"),
    Column("name", String(200), nullable=False),
    Column("search_key", String(200), nullable=False, unique=True,
           default=place_key_default),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False,
           server_default=func.now(), onupdate=func.now()),
    CheckConstraint("length(trim(name)) > 0", name="place_name_not_blank"),
    CheckConstraint("length(trim(search_key)) > 0", name="place_key_not_blank"),
)

suppliers = Table(
    "suppliers",
    metadata,
    Column("id", Uuid, primary_key=True, default=uuid4),
    Column("name", String(200), nullable=False),
    Column("supplier_type", String(50), nullable=False),
    Column("tags", SupplierTags(), nullable=False, default=list,
           server_default=text("'{}'::text[]")),
    Column("place_id", Uuid, ForeignKey("places.id", ondelete="RESTRICT"), nullable=False),
    Column("floor", String(30)),
    Column("location_description", Text),
    Column("latitude", Float),
    Column("longitude", Float),
    # Required, so callers never treat unknown hours as a special case.
    # A closing time before the opening time means trading past midnight; see
    # "Opening hours" in the README before querying these as a range.
    Column("opening_time", Time, nullable=False),
    Column("closing_time", Time, nullable=False),
    Column("image_url", Text),
    Column("pickup_instructions", Text),
    Column("is_active", Boolean, nullable=False, server_default=true()),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False,
           server_default=func.now(), onupdate=func.now()),
    CheckConstraint("length(trim(name)) > 0", name="supplier_name_not_blank"),
    CheckConstraint(f"cardinality(tags) <= {MAX_TAGS}", name="supplier_tag_count"),
    CheckConstraint("COALESCE(array_ndims(tags), 1) = 1", name="supplier_tags_one_dimension"),
    CheckConstraint("array_position(tags, NULL) IS NULL", name="supplier_tags_no_null_elements"),
    CheckConstraint("latitude BETWEEN -90 AND 90", name="supplier_latitude_range"),
    CheckConstraint("longitude BETWEEN -180 AND 180", name="supplier_longitude_range"),
)

suppliers.append_constraint(CheckConstraint(
    suppliers.c.supplier_type.in_(SUPPLIER_TYPES), name="supplier_type_allowed"
))

AUDIT_ENTITIES = ("SUPPLIER", "PLACE")
AUDIT_ACTIONS = (
    "SUPPLIER_CREATED", "SUPPLIER_UPDATED", "SUPPLIER_DEACTIVATED", "PLACE_CREATED",
)

# Who changed what, and why. Written in the same transaction as the change.
# User Service keeps its own separate log of account changes.
supplier_audit_logs = Table(
    "supplier_audit_logs",
    metadata,
    Column("id", Uuid, primary_key=True, default=uuid4),
    # A User Service id, so no foreign key: that table is in another database.
    Column("acting_admin_user_id", Uuid, nullable=False),
    Column("entity_type", String(20), nullable=False),
    # No foreign key: this points at either a supplier or a place.
    Column("entity_id", Uuid, nullable=False),
    Column("action_type", String(40), nullable=False),
    Column("previous_value", JSONB, nullable=False),
    Column("new_value", JSONB, nullable=False),
    # Null on a create; required when changing or hiding a record.
    Column("reason", String(500)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("reason IS NULL OR length(trim(reason)) > 0",
                    name="supplier_audit_reason_not_blank"),
)

supplier_audit_logs.append_constraint(CheckConstraint(
    supplier_audit_logs.c.entity_type.in_(AUDIT_ENTITIES),
    name="supplier_audit_entity_allowed",
))
supplier_audit_logs.append_constraint(CheckConstraint(
    supplier_audit_logs.c.action_type.in_(AUDIT_ACTIONS),
    name="supplier_audit_action_allowed",
))

# One supplier per name, place and floor, ignoring capitals, spaces and
# punctuation so a re-spelling is not a new record. COALESCE makes an unknown
# floor a value rather than "any floor".
SUPPLIER_NAME_KEY = func.lower(
    func.regexp_replace(suppliers.c.name, "[^a-zA-Z0-9]", "", "g")
)

Index(
    "uq_supplier_key_place_floor",
    SUPPLIER_NAME_KEY,
    suppliers.c.place_id,
    func.coalesce(suppliers.c.floor, ""),
    unique=True,
)

Index("ix_suppliers_place", suppliers.c.place_id)
Index("ix_suppliers_type", suppliers.c.supplier_type)

Index("ix_places_parent", places.c.parent_id)

# The audit log is read newest-first, and filtered to one record's history.
Index("ix_supplier_audit_logs_created", supplier_audit_logs.c.created_at.desc())
Index("ix_supplier_audit_logs_entity",
      supplier_audit_logs.c.entity_type, supplier_audit_logs.c.entity_id)
