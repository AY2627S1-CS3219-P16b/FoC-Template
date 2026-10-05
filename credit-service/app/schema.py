"""Credit records owned by the Credit Service."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    func,
)

metadata = MetaData()

credit_accounts = Table(
    "credit_accounts",
    metadata,
    Column("user_id", String, primary_key=True),
    Column("available_balance", Integer, nullable=False),
    Column("reserved_balance", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),
    CheckConstraint("available_balance >= 0", name="ck_credit_accounts_available_non_negative"),
    CheckConstraint("reserved_balance >= 0", name="ck_credit_accounts_reserved_non_negative"),
)

credit_reservations = Table(
    "credit_reservations",
    metadata,
    Column("id", String, primary_key=True),
    Column("order_id", String, nullable=False),
    Column("requester_user_id", String, nullable=False),
    Column("courier_user_id", String, nullable=True),
    Column("amount", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),
    UniqueConstraint("order_id", name="uq_credit_reservations_order_id"),
    CheckConstraint("amount > 0", name="ck_credit_reservations_amount_positive"),
    CheckConstraint(
        "status in ('RESERVED', 'RELEASED', 'TRANSFERRED')",
        name="ck_credit_reservations_status",
    ),
    CheckConstraint(
        "courier_user_id is null or courier_user_id <> requester_user_id",
        name="ck_credit_reservations_distinct_users",
    ),
    Index("ix_credit_reservations_requester_user_id", "requester_user_id"),
    Index("ix_credit_reservations_courier_user_id", "courier_user_id"),
)

credit_ledger_entries = Table(
    "credit_ledger_entries",
    metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, nullable=False),
    Column("order_id", String, nullable=True),
    Column("type", String, nullable=False),
    Column("amount", Integer, nullable=False),
    Column("available_balance_after", Integer, nullable=False),
    Column("reserved_balance_after", Integer, nullable=False),
    Column("reservation_id", String, nullable=True),
    Column("idempotency_key", String, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("idempotency_key", name="uq_credit_ledger_entries_idempotency_key"),
    CheckConstraint(
        "type in ("
        "'INITIAL_ALLOCATION', "
        "'CREDIT_RESERVED', "
        "'CREDIT_RELEASED', "
        "'CREDIT_TRANSFERRED_IN', "
        "'CREDIT_TRANSFERRED_OUT'"
        ")",
        name="ck_credit_ledger_entries_type",
    ),
    CheckConstraint(
        "available_balance_after >= 0",
        name="ck_credit_ledger_entries_available_after_non_negative",
    ),
    CheckConstraint(
        "reserved_balance_after >= 0",
        name="ck_credit_ledger_entries_reserved_after_non_negative",
    ),
    Index("ix_credit_ledger_entries_user_created", "user_id", "created_at"),
    Index("ix_credit_ledger_entries_order_id", "order_id"),
)

# Backwards-compatible alias while the service is still being built.
credit_ledgers = credit_ledger_entries
