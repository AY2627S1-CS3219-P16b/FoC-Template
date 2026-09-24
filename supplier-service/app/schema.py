"""Supplier records owned by the Supplier Service."""

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, MetaData,
    String, Table, Text, Time, UniqueConstraint, Uuid, func, text, true,
)
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
    Column("opening_time", Time),
    Column("closing_time", Time),
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
    UniqueConstraint("name", "place_id", "floor", name="uq_supplier_name_place_floor",
                     postgresql_nulls_not_distinct=True),
)

suppliers.append_constraint(CheckConstraint(
    suppliers.c.supplier_type.in_(SUPPLIER_TYPES), name="supplier_type_allowed"
))

Index("ix_suppliers_place", suppliers.c.place_id)
Index("ix_suppliers_type", suppliers.c.supplier_type)
Index("ix_suppliers_tags", suppliers.c.tags, postgresql_using="gin")

Index("ix_places_parent", places.c.parent_id)
