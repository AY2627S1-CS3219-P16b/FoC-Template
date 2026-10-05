"""Credit database operations. Every change is recorded in the credit ledger log."""

from datetime import date, datetime, time
import os
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from .schema import credit_reservations, credit_ledger_entries, credit_accounts


class UserError(Exception):
    """This user does not exist."""


class InsufficientCredits(Exception):
    """The user does not have sufficient funds to complete the transaction."""


class NoChangeError(Exception):
    """The request would leave the record exactly as it is."""


class DuplicateReservationError(Exception):
    """A credit reservation already exists for this order."""


class ReservationNotFoundError(Exception):
    """A credit reservation does not exist for this order."""


class ReservationStateError(Exception):
    """The reservation is not in the required state for this operation."""


def _json_safe(value):
    """Values as JSON types, since times and UUIDs cannot be stored directly."""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def _required_text(value: str | UUID, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must not be blank")
    return text


def _positive_amount(amount: int) -> int:
    if isinstance(amount, bool):
        raise ValueError("amount must be a positive integer")
    amount_int = int(amount)
    if amount_int <= 0:
        raise ValueError("amount must be a positive integer")
    return amount_int


def _initial_credits() -> int:
    value = int(os.getenv("INITIAL_CREDITS", "20"))
    if value < 0:
        raise RuntimeError("INITIAL_CREDITS must be zero or greater")
    return value


def get_account(connection: Connection, user_id: str | UUID) -> dict[str, object]:
    user_id_text = _required_text(user_id, "user_id")
    row = connection.execute(
        select(credit_accounts).where(credit_accounts.c.user_id == user_id_text)
    ).mappings().one_or_none()
    if row is None:
        raise UserError(f"Credit account does not exist for user {user_id_text}.")
    return dict(row)


def ensure_account(
    connection: Connection,
    user_id: str | UUID,
    initial_credits: int | None = None,
) -> dict[str, object]:
    """Return the user's credit account, creating the initial allocation if needed."""
    user_id_text = _required_text(user_id, "user_id")
    existing = connection.execute(
        select(credit_accounts).where(credit_accounts.c.user_id == user_id_text)
    ).mappings().one_or_none()
    if existing is not None:
        return dict(existing)

    starting_balance = _initial_credits() if initial_credits is None else initial_credits
    if starting_balance < 0:
        raise ValueError("initial_credits must be zero or greater")

    connection.execute(
        insert(credit_accounts).values(
            user_id=user_id_text,
            available_balance=starting_balance,
            reserved_balance=0,
        )
    )
    connection.execute(
        insert(credit_ledger_entries).values(
            id=str(uuid4()),
            user_id=user_id_text,
            order_id=None,
            type="INITIAL_ALLOCATION",
            amount=starting_balance,
            available_balance_after=starting_balance,
            reserved_balance_after=0,
            reservation_id=None,
            idempotency_key=f"initial-allocation:{user_id_text}",
        )
    )
    return get_account(connection, user_id_text)


def reserve_credits(
    connection: Connection,
    order_id: str,
    requester_user_id: str | UUID,
    amount: int,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    """Reserve requester credits for an order.

    This moves credits from available to reserved balance, creates exactly one
    reservation for the order, and records the movement in the ledger.
    """
    order_id_text = _required_text(order_id, "order_id")
    requester_user_id_text = _required_text(requester_user_id, "requester_user_id")
    amount_int = _positive_amount(amount)

    existing = connection.execute(
        select(credit_reservations).where(
            credit_reservations.c.order_id == order_id_text
        )
    ).mappings().one_or_none()

    if existing is not None:
        if (
            existing["requester_user_id"] == requester_user_id_text
            and existing["amount"] == amount_int
            and existing["status"] == "RESERVED"
        ):
            return dict(existing)
        raise DuplicateReservationError(
            f"Credit reservation already exists for order {order_id_text}."
        )

    ensure_account(connection, requester_user_id_text)
    account = connection.execute(
        select(credit_accounts)
        .where(credit_accounts.c.user_id == requester_user_id_text)
        .with_for_update()
    ).mappings().one()

    available_balance = account["available_balance"]
    reserved_balance = account["reserved_balance"]
    if available_balance < amount_int:
        raise InsufficientCredits(
            f"User {requester_user_id_text} has insufficient available credits."
        )

    reservation_id = str(uuid4())
    new_available_balance = available_balance - amount_int
    new_reserved_balance = reserved_balance + amount_int
    ledger_idempotency_key = idempotency_key or f"reserve:{order_id_text}"

    connection.execute(
        update(credit_accounts)
        .where(credit_accounts.c.user_id == requester_user_id_text)
        .values(
            available_balance=new_available_balance,
            reserved_balance=new_reserved_balance,
        )
    )
    try:
        connection.execute(
            insert(credit_reservations).values(
                id=reservation_id,
                order_id=order_id_text,
                requester_user_id=requester_user_id_text,
                courier_user_id=None,
                amount=amount_int,
                status="RESERVED",
            )
        )
        connection.execute(
            insert(credit_ledger_entries).values(
                id=str(uuid4()),
                user_id=requester_user_id_text,
                order_id=order_id_text,
                type="CREDIT_RESERVED",
                amount=-amount_int,
                available_balance_after=new_available_balance,
                reserved_balance_after=new_reserved_balance,
                reservation_id=reservation_id,
                idempotency_key=ledger_idempotency_key,
            )
        )
    except IntegrityError as error:
        raise DuplicateReservationError(
            f"Credit reservation already exists for order {order_id_text}."
        ) from error

    return dict(
        connection.execute(
            select(credit_reservations).where(credit_reservations.c.id == reservation_id)
        ).mappings().one()
    )


def list_ledger(
    connection: Connection,
    user_id: str | UUID,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, object]:
    user_id_text = _required_text(user_id, "user_id")
    if page < 1:
        raise ValueError("page must be greater than or equal to 1")
    if page_size < 1 or page_size > 100:
        raise ValueError("page_size must be between 1 and 100")

    get_account(connection, user_id_text)
    total = connection.execute(
        select(func.count())
        .select_from(credit_ledger_entries)
        .where(credit_ledger_entries.c.user_id == user_id_text)
    ).scalar_one()
    offset = (page - 1) * page_size
    rows = connection.execute(
        select(credit_ledger_entries)
        .where(credit_ledger_entries.c.user_id == user_id_text)
        .order_by(credit_ledger_entries.c.created_at.desc(), credit_ledger_entries.c.id.desc())
        .limit(page_size)
        .offset(offset)
    ).mappings().all()
    return {
        "items": [dict(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
    }


def release_reservation(
    connection: Connection,
    order_id: str,
    requester_user_id: str | UUID,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    """Release reserved credits after an order is cancelled or expires."""
    order_id_text = _required_text(order_id, "order_id")
    requester_user_id_text = _required_text(requester_user_id, "requester_user_id")

    reservation = connection.execute(
        select(credit_reservations)
        .where(credit_reservations.c.order_id == order_id_text)
        .with_for_update()
    ).mappings().one_or_none()
    if reservation is None:
        raise ReservationNotFoundError(
            f"Credit reservation does not exist for order {order_id_text}."
        )
    if reservation["requester_user_id"] != requester_user_id_text:
        raise ReservationStateError("Only the reservation requester can release credits.")
    if reservation["status"] == "RELEASED":
        return dict(reservation)
    if reservation["status"] != "RESERVED":
        raise ReservationStateError(
            f"Cannot release a reservation with status {reservation['status']}."
        )

    account = connection.execute(
        select(credit_accounts)
        .where(credit_accounts.c.user_id == requester_user_id_text)
        .with_for_update()
    ).mappings().one_or_none()
    if account is None:
        raise UserError(f"Credit account does not exist for user {requester_user_id_text}.")

    amount = reservation["amount"]
    if account["reserved_balance"] < amount:
        raise ReservationStateError("Reserved balance is lower than reservation amount.")

    new_available_balance = account["available_balance"] + amount
    new_reserved_balance = account["reserved_balance"] - amount
    ledger_idempotency_key = idempotency_key or f"release:{order_id_text}"

    connection.execute(
        update(credit_accounts)
        .where(credit_accounts.c.user_id == requester_user_id_text)
        .values(
            available_balance=new_available_balance,
            reserved_balance=new_reserved_balance,
        )
    )
    connection.execute(
        update(credit_reservations)
        .where(credit_reservations.c.order_id == order_id_text)
        .values(
            status="RELEASED",
        )
    )
    connection.execute(
        insert(credit_ledger_entries).values(
            id=str(uuid4()),
            user_id=requester_user_id_text,
            order_id=order_id_text,
            type="CREDIT_RELEASED",
            amount=amount,
            available_balance_after=new_available_balance,
            reserved_balance_after=new_reserved_balance,
            reservation_id=reservation["id"],
            idempotency_key=ledger_idempotency_key,
        )
    )

    return dict(
        connection.execute(
            select(credit_reservations).where(
                credit_reservations.c.order_id == order_id_text
            )
        ).mappings().one()
    )


def transfer_reservation(
    connection: Connection,
    order_id: str,
    requester_user_id: str | UUID,
    courier_user_id: str | UUID,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    """Transfer reserved credits from requester to courier after completion."""
    order_id_text = _required_text(order_id, "order_id")
    requester_user_id_text = _required_text(requester_user_id, "requester_user_id")
    courier_user_id_text = _required_text(courier_user_id, "courier_user_id")
    if requester_user_id_text == courier_user_id_text:
        raise ReservationStateError("Requester cannot receive credits as courier.")

    reservation = connection.execute(
        select(credit_reservations)
        .where(credit_reservations.c.order_id == order_id_text)
        .with_for_update()
    ).mappings().one_or_none()
    if reservation is None:
        raise ReservationNotFoundError(
            f"Credit reservation does not exist for order {order_id_text}."
        )
    if reservation["requester_user_id"] != requester_user_id_text:
        raise ReservationStateError("Only the reservation requester can transfer credits.")
    if reservation["status"] == "TRANSFERRED":
        if reservation["courier_user_id"] == courier_user_id_text:
            return dict(reservation)
        raise ReservationStateError("Reservation was already transferred to another courier.")
    if reservation["status"] != "RESERVED":
        raise ReservationStateError(
            f"Cannot transfer a reservation with status {reservation['status']}."
        )

    requester_account = connection.execute(
        select(credit_accounts)
        .where(credit_accounts.c.user_id == requester_user_id_text)
        .with_for_update()
    ).mappings().one_or_none()
    if requester_account is None:
        raise UserError(f"Credit account does not exist for user {requester_user_id_text}.")

    ensure_account(connection, courier_user_id_text)
    courier_account = connection.execute(
        select(credit_accounts)
        .where(credit_accounts.c.user_id == courier_user_id_text)
        .with_for_update()
    ).mappings().one_or_none()
    if courier_account is None:
        raise UserError(f"Credit account does not exist for user {courier_user_id_text}.")

    amount = reservation["amount"]
    if requester_account["reserved_balance"] < amount:
        raise ReservationStateError("Requester reserved balance is lower than reservation amount.")

    requester_reserved_after = requester_account["reserved_balance"] - amount
    courier_available_after = courier_account["available_balance"] + amount
    transfer_key = idempotency_key or f"transfer:{order_id_text}"

    connection.execute(
        update(credit_accounts)
        .where(credit_accounts.c.user_id == requester_user_id_text)
        .values(reserved_balance=requester_reserved_after)
    )
    connection.execute(
        update(credit_accounts)
        .where(credit_accounts.c.user_id == courier_user_id_text)
        .values(available_balance=courier_available_after)
    )
    connection.execute(
        update(credit_reservations)
        .where(credit_reservations.c.order_id == order_id_text)
        .values(
            courier_user_id=courier_user_id_text,
            status="TRANSFERRED",
        )
    )
    connection.execute(
        insert(credit_ledger_entries).values(
            id=str(uuid4()),
            user_id=requester_user_id_text,
            order_id=order_id_text,
            type="CREDIT_TRANSFERRED_OUT",
            amount=-amount,
            available_balance_after=requester_account["available_balance"],
            reserved_balance_after=requester_reserved_after,
            reservation_id=reservation["id"],
            idempotency_key=f"{transfer_key}:out",
        )
    )
    connection.execute(
        insert(credit_ledger_entries).values(
            id=str(uuid4()),
            user_id=courier_user_id_text,
            order_id=order_id_text,
            type="CREDIT_TRANSFERRED_IN",
            amount=amount,
            available_balance_after=courier_available_after,
            reserved_balance_after=courier_account["reserved_balance"],
            reservation_id=reservation["id"],
            idempotency_key=f"{transfer_key}:in",
        )
    )

    return dict(
        connection.execute(
            select(credit_reservations).where(
                credit_reservations.c.order_id == order_id_text
            )
        ).mappings().one()
    )
