"""Order records, operation history, and durable credit work.
"""

from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    column,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

# all possible statuses of an order
ORDER_STATUSES = (
    "RESERVING", "OPEN", "ACCEPTED", "PICKED_UP", "DELIVERED",
    "COMPLETING", "COMPLETED", "CANCELLING", "CANCELLED",
    "EXPIRING", "EXPIRED", "REJECTED",
)
CREDIT_OPERATIONS = ("RESERVE", "RELEASE", "TRANSFER")
LOG_OUTCOMES = ("SUCCEEDED", "REJECTED", "FAILED")

metadata = MetaData()

# main table containing all orders
orders = Table(
    "orders",
    metadata,
    Column("id", String, primary_key=True, default=lambda: str(uuid4())),
    # These records belong to other services, so they have no local foreign keys.
    Column("requester_user_id", String, nullable=False),
    Column("courier_user_id", String, nullable=True),
    Column("supplier_id", String, nullable=False),
    # Capture pickup details at creation so later supplier edits do not rewrite orders.
    Column("supplier_name", String(200), nullable=False),
    Column("pickup_location", Text, nullable=False),
    Column("item_description", Text, nullable=False),
    Column("delivery_location", Text, nullable=False),
    Column("delivery_instructions", Text, nullable=True),
    Column("credit_amount", Integer, nullable=False),
    Column("status", String(20), nullable=False, server_default="RESERVING"),
    # Deadline for acceptance, not delivery.
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    ),
    Column("idempotency_key", String(200), nullable=False),
    UniqueConstraint(
        "requester_user_id", "idempotency_key", name="uq_orders_requester_idempotency_key",
    ),
    CheckConstraint("credit_amount > 0", name="ck_orders_credit_amount_positive"),
    CheckConstraint(
        "courier_user_id IS NULL OR courier_user_id <> requester_user_id",
        name="ck_orders_distinct_users",
    ),
    CheckConstraint(
        "(status IN ('ACCEPTED', 'PICKED_UP', 'DELIVERED', 'COMPLETING', 'COMPLETED') "
        "AND courier_user_id IS NOT NULL) OR "
        "(status IN ('RESERVING', 'OPEN', 'CANCELLING', 'CANCELLED', "
        "'EXPIRING', 'EXPIRED', 'REJECTED') AND courier_user_id IS NULL)",
        name="ck_orders_courier_matches_status",
    ),
    CheckConstraint("expires_at > created_at", name="ck_orders_expiry_after_creation"),
    CheckConstraint("updated_at >= created_at", name="ck_orders_updated_after_creation"),
    CheckConstraint(column("status").in_(ORDER_STATUSES), name="ck_orders_status"),
    CheckConstraint("length(trim(id)) > 0", name="ck_orders_id_not_blank"),
    CheckConstraint("length(trim(requester_user_id)) > 0", name="ck_orders_requester_user_id_not_blank"),
    CheckConstraint("length(trim(supplier_id)) > 0", name="ck_orders_supplier_id_not_blank"),
    CheckConstraint("length(trim(supplier_name)) > 0", name="ck_orders_supplier_name_not_blank"),
    CheckConstraint("length(trim(pickup_location)) > 0", name="ck_orders_pickup_location_not_blank"),
    CheckConstraint("length(trim(item_description)) > 0", name="ck_orders_item_description_not_blank"),
    CheckConstraint("length(trim(delivery_location)) > 0", name="ck_orders_delivery_location_not_blank"),
    CheckConstraint("length(trim(idempotency_key)) > 0", name="ck_orders_idempotency_key_not_blank"),
    CheckConstraint(
        "courier_user_id IS NULL OR length(trim(courier_user_id)) > 0",
        name="ck_orders_courier_not_blank",
    ),
)

order_log = Table(
    "order_log",
    metadata,
    Column("id", String, primary_key=True, default=lambda: str(uuid4())),
    Column("order_id", String, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
    # Null for system actions such as expiry and credit-job processing.
    Column("actor_user_id", String, nullable=True),
    Column("action", String(50), nullable=False),
    Column("outcome", String(20), nullable=False, server_default="SUCCEEDED"),
    Column("previous_status", String(20), nullable=True),
    Column("new_status", String(20), nullable=True),
    Column("details", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("length(trim(action)) > 0", name="ck_order_log_action_not_blank"),
    CheckConstraint(
        "actor_user_id IS NULL OR length(trim(actor_user_id)) > 0",
        name="ck_order_log_actor_not_blank",
    ),
    CheckConstraint("jsonb_typeof(details) = 'object'", name="ck_order_log_details_object"),
    CheckConstraint(
        column("previous_status").in_(ORDER_STATUSES), name="ck_order_log_previous_status",
    ),
    CheckConstraint(column("new_status").in_(ORDER_STATUSES), name="ck_order_log_new_status"),
    CheckConstraint(column("outcome").in_(LOG_OUTCOMES), name="ck_order_log_outcome"),
)

# Insert a job in the same transaction as its corresponding pending order state.
# Mark it complete in the same transaction as the final order-state update.
credit_jobs = Table(
    "credit_jobs",
    metadata,
    Column("id", String, primary_key=True, default=lambda: str(uuid4())),
    Column("order_id", String, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
    Column("operation", String(20), nullable=False),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("next_attempt_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("last_error_code", String(100), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("order_id", "operation", name="uq_credit_jobs_order_operation"),
    CheckConstraint("attempts >= 0", name="ck_credit_jobs_attempts_non_negative"),
    CheckConstraint(
        "completed_at IS NULL OR completed_at >= created_at",
        name="ck_credit_jobs_completed_after_creation",
    ),
    CheckConstraint(column("operation").in_(CREDIT_OPERATIONS), name="ck_credit_jobs_operation"),
)

# List one requester's orders, newest first.
Index("ix_orders_requester_created", orders.c.requester_user_id, orders.c.created_at.desc())
# List one courier's assigned orders, newest first.
Index("ix_orders_courier_created", orders.c.courier_user_id, orders.c.created_at.desc())
# Filter by status and acceptance deadline, including OPEN orders due to expire.
Index("ix_orders_status_expiry", orders.c.status, orders.c.expires_at)
# Read one order's history chronologically
Index("ix_order_log_order_created", order_log.c.order_id, order_log.c.created_at, order_log.c.id)
# Find due credit jobs by next retry time, then creation time. 
Index(
    "ix_credit_jobs_pending", credit_jobs.c.next_attempt_at, credit_jobs.c.created_at,
    postgresql_where=credit_jobs.c.completed_at.is_(None),
)
