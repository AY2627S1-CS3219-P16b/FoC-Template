"""Supplier records owned by the Supplier Service."""

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Float, Index, MetaData,
    String, Table, Text, Time, Uuid, func, true,
)
from uuid import uuid4


metadata = MetaData()

suppliers = Table(
    "suppliers",
    metadata,
    Column("id", Uuid, primary_key=True, default=uuid4),
    Column("name", String(200), nullable=False),
    Column("supplier_type", String(50), nullable=False),
    Column("building", String(200), nullable=False),
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
    CheckConstraint("length(trim(supplier_type)) > 0", name="supplier_type_not_blank"),
    CheckConstraint("length(trim(building)) > 0", name="supplier_building_not_blank"),
    CheckConstraint("latitude BETWEEN -90 AND 90", name="supplier_latitude_range"),
    CheckConstraint("longitude BETWEEN -180 AND 180", name="supplier_longitude_range"),
)

Index("ix_suppliers_building", suppliers.c.building)
Index("ix_suppliers_type", suppliers.c.supplier_type)
