"""Transactional order operations and durable credit jobs.

Endpoints supply user IDs from verified JWTs and enforce role mode. Operations
must check ownership, assignment and lifecycle state. Mutations must write
order_log in the same transaction. Credit work is queued for a separate worker.
Paginated reads return items, page, page_size, total and total_pages.
"""

from datetime import datetime
import json
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import func, insert, or_, select, text, update
from sqlalchemy.engine import Connection

from .schema import ORDER_STATUSES, credit_jobs, order_log, orders


class OrderIdempotencyConflict(ValueError):
    """An existing request key was reused with different order details (HTTP 409)."""


class OrderNotFoundError(LookupError):
    """The requested order does not exist (HTTP 404)."""


class OrderAccessDeniedError(PermissionError):
    """The caller cannot access the requested order data (HTTP 403)."""


class OrderStateError(ValueError):
    """The order's current state does not allow this operation (HTTP 409)."""


def _required_text(value: str | UUID, field_name: str) -> str:
    if not isinstance(value, (str, UUID)):
        raise ValueError(f"{field_name} must be text or a UUID")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must not be blank")
    return text


def _page(connection: Connection, statement, page: int, page_size: int) -> dict[str, object]:
    if type(page) is not int or page < 1:
        raise ValueError("page must be a positive integer")
    if type(page_size) is not int or not 1 <= page_size <= 100:
        raise ValueError("page_size must be an integer between 1 and 100")
    total = connection.execute(select(func.count()).select_from(
        statement.order_by(None).subquery(),
    )).scalar_one()
    rows = connection.execute(statement.offset((page - 1) * page_size).limit(page_size)).mappings().all()
    return {"items": [dict(row) for row in rows], "page": page, "page_size": page_size,
            "total": total, "total_pages": (total + page_size - 1) // page_size}


def create_order(
    connection: Connection,
    *,
    requester_user_id: str,
    supplier_id: str,
    supplier_name: str,
    pickup_location: str,
    item_description: str,
    delivery_location: str,
    credit_amount: int,
    expires_at: datetime,
    idempotency_key: str,
    delivery_instructions: str | None = None,
) -> dict[str, object]:
    """Create RESERVING order and RESERVE job, or return an identical retry.

    Supplier name/location come from Supplier Service. Generate the order ID
    here; publish OPEN only after reservation succeeds. The caller owns the
    transaction (use engine.begin()); this function never commits it. A savepoint
    keeps the order, log and job atomic even if the caller catches an exception.
    Identical retries return the current order, including after expiry.
    """
    values = {
        "requester_user_id": _required_text(requester_user_id, "requester_user_id"),
        "supplier_id": _required_text(supplier_id, "supplier_id"),
        "supplier_name": _required_text(supplier_name, "supplier_name"),
        "pickup_location": _required_text(pickup_location, "pickup_location"),
        "item_description": _required_text(item_description, "item_description"),
        "delivery_location": _required_text(delivery_location, "delivery_location"),
        "idempotency_key": _required_text(idempotency_key, "idempotency_key"),
    }
    for field, limit in (
        ("requester_user_id", 100), ("supplier_id", 100),
        ("supplier_name", 200), ("idempotency_key", 200),
    ):
        if len(values[field]) > limit:
            raise ValueError(f"{field} must be at most {limit} characters")
    if type(credit_amount) is not int or not 0 < credit_amount <= 2147483647:
        raise ValueError("credit_amount must be a positive 32-bit integer")
    if not isinstance(expires_at, datetime) or expires_at.utcoffset() is None:
        raise ValueError("expires_at must be a timezone-aware datetime")
    if delivery_instructions is not None and not isinstance(delivery_instructions, str):
        raise ValueError("delivery_instructions must be text or None")
    values.update(
        credit_amount=credit_amount,
        expires_at=expires_at,
        delivery_instructions=(delivery_instructions.strip() or None)
        if delivery_instructions is not None else None,
    )

    with connection.begin_nested():
        # Serialize first creation as well as retries for this requester/key.
        # Hash collisions only serialize unrelated requests; they cannot mix them.
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": json.dumps([values["requester_user_id"], values["idempotency_key"]])},
        )
        existing = connection.execute(
            select(orders).where(
                orders.c.requester_user_id == values["requester_user_id"],
                orders.c.idempotency_key == values["idempotency_key"],
            )
        ).mappings().one_or_none()
        if existing is not None:
            # Supplier snapshots are server-owned and may change between retries.
            if any(existing[field] != value for field, value in values.items()
                   if field not in ("supplier_name", "pickup_location")):
                raise OrderIdempotencyConflict(
                    "Idempotency key is already used for different order details."
                )
            return dict(existing)

        # Use database time so expiry validation and stored timestamps agree.
        now = connection.execute(select(func.clock_timestamp())).scalar_one()
        if expires_at <= now:
            raise ValueError("expires_at must be in the future")
        order_id = str(uuid4())
        created = connection.execute(
            insert(orders).values(
                **values, id=order_id, courier_user_id=None,
                status="RESERVING", created_at=now, updated_at=now,
            ).returning(orders)
        ).mappings().one()
        connection.execute(
            insert(order_log).values(
                order_id=order_id, actor_user_id=values["requester_user_id"],
                action="CREATE_ORDER", outcome="SUCCEEDED", previous_status=None,
                new_status="RESERVING", details={}, created_at=now,
            )
        )
        connection.execute(
            insert(credit_jobs).values(
                order_id=order_id, operation="RESERVE", attempts=0,
                next_attempt_at=now, created_at=now,
            )
        )
        return dict(created)


def list_orders(
    connection: Connection,
    *,
    viewer_user_id: str,
    status: str = "OPEN",
    supplier_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, object]:
    """List matching orders, newest first, with pagination metadata.

    Unexpired OPEN orders are visible to all authenticated users. Other statuses
    are visible only to the requester or assigned courier. Expired OPEN orders
    are excluded until the expiry worker transitions them.
    """
    viewer_user_id = _required_text(viewer_user_id, "viewer_user_id")
    status = _required_text(status, "status")
    if status not in ORDER_STATUSES:
        raise ValueError("status must be a valid order status")
    filters = [orders.c.status == status]
    if status == "OPEN":
        filters.append(orders.c.expires_at > func.statement_timestamp())
    else:
        filters.append(or_(
            orders.c.requester_user_id == viewer_user_id,
            orders.c.courier_user_id == viewer_user_id,
        ))
    if supplier_id is not None:
        supplier_id = _required_text(supplier_id, "supplier_id")
        filters.append(orders.c.supplier_id == supplier_id)

    return _page(connection,
        select(orders)
        .where(*filters)
        .order_by(orders.c.created_at.desc(), orders.c.id.desc()), page, page_size,
    )


def list_admin_orders(
    connection: Connection,
    *,
    requester_user_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, object]:
    """List all orders for a caller authorized by the endpoint as an admin."""
    filters = []
    if requester_user_id is not None:
        filters.append(orders.c.requester_user_id == _required_text(
            requester_user_id, "requester_user_id",
        ))
    if status is not None:
        if status not in ORDER_STATUSES:
            raise ValueError("status must be a valid order status")
        filters.append(orders.c.status == status)
    return _page(connection, select(orders).where(*filters).order_by(
        orders.c.created_at.desc(), orders.c.id.desc(),
    ), page, page_size)


def get_user_orders(
    connection: Connection,
    user_id: str,
    *,
    role: Literal["requester", "courier"],
    status: str | None = None,
    view: Literal["active", "past", "all"] = "all",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, object]:
    """List the caller's requests or courier assignments, newest first."""
    user_id = _required_text(user_id, "user_id")
    role = _required_text(role, "role")

    if status is not None:
        status = _required_text(status, "status")
        if status not in ORDER_STATUSES:
            raise ValueError("status must be a valid order status")
    if role not in {"requester", "courier"}:
        raise ValueError("role must be a valid role")
    if view not in {"active", "past", "all"}:
        raise ValueError("view must be active, past or all")
    owner_column = (
        orders.c.requester_user_id if role == "requester" else orders.c.courier_user_id
    )
    filters = [owner_column == user_id]
    past_statuses = ("COMPLETED", "CANCELLED", "EXPIRED", "REJECTED")
    if view == "active":
        filters.append(orders.c.status.not_in(past_statuses))
    elif view == "past":
        filters.append(orders.c.status.in_(past_statuses))
    if status is not None:
        filters.append(orders.c.status == status)

    return _page(connection,
        select(orders)
        .where(*filters)
        .order_by(orders.c.created_at.desc(), orders.c.id.desc()), page, page_size,
    )


def get_order_details(
    connection: Connection,
    order_id: str,
    *,
    viewer_user_id: str,
) -> dict[str, object]:
    """Read an order visible to its participants or to an authenticated browser.

    Requesters and assigned couriers can read their orders in any state. Other
    users can only read unexpired OPEN orders, matching browse visibility.
    """
    viewer_user_id = _required_text(viewer_user_id, "viewer_user_id")
    order_id = _required_text(order_id, "order_id")

    row = connection.execute(
        select(
            orders,
            (
                (orders.c.status == "OPEN")
                & (orders.c.expires_at > func.statement_timestamp())
            ).label("is_browsable"),
        ).where(orders.c.id == order_id)
    ).mappings().one_or_none()
    if row is None:
        raise OrderNotFoundError("Order does not exist.")

    order = dict(row)
    is_browsable = order.pop("is_browsable")
    is_participant = viewer_user_id in (
        order["requester_user_id"], order["courier_user_id"],
    )
    if not is_participant and not is_browsable:
        raise OrderAccessDeniedError(
            "Only the requester or assigned courier can read this order."
        )
    return order


def assign_courier(
    connection: Connection,
    order_id: str,
    *,
    courier_user_id: str,
) -> dict[str, object]:
    """Atomically accept an unexpired OPEN order, excluding its requester.

    Lock the order until the caller's transaction ends. Update the assignment
    and history together; successful retries at later stages add no new log.
    The endpoint must verify courier role mode and supply the JWT's user ID.
    """
    courier_user_id = _required_text(courier_user_id, "courier_user_id")
    order_id = _required_text(order_id, "order_id")

    with connection.begin_nested():
        order = connection.execute(
            select(orders).where(orders.c.id == order_id).with_for_update()
        ).mappings().one_or_none()
        if order is None:
            raise OrderNotFoundError("Order does not exist.")
        if courier_user_id == order["requester_user_id"]:
            raise OrderAccessDeniedError("Requesters cannot accept their own orders.")
        if (order["courier_user_id"] == courier_user_id and order["status"] in
                ("ACCEPTED", "PICKED_UP", "DELIVERED", "COMPLETING", "COMPLETED")):
            return dict(order)
        if order["status"] != "OPEN" or order["courier_user_id"] is not None:
            raise OrderStateError("Only an unassigned OPEN order can be accepted.")

        # Read current database time after acquiring the lock: waiting for another
        # transaction must not let a courier accept an order past its deadline.
        now = connection.execute(select(func.clock_timestamp())).scalar_one()
        if order["expires_at"] <= now:
            raise OrderStateError("The order's acceptance deadline has passed.")

        accepted = connection.execute(
            update(orders)
            .where(orders.c.id == order_id)
            .values(courier_user_id=courier_user_id, status="ACCEPTED", updated_at=now)
            .returning(orders)
        ).mappings().one()
        connection.execute(
            insert(order_log).values(
                order_id=order_id, actor_user_id=courier_user_id,
                action="ACCEPT_ORDER", outcome="SUCCEEDED", previous_status="OPEN",
                new_status="ACCEPTED", details={}, created_at=now,
            )
        )
        return dict(accepted)


def _advance_courier_order(
    connection: Connection,
    order_id: str,
    courier_user_id: str,
    *,
    previous_status: str,
    next_status: str,
    action: str,
) -> dict[str, object]:
    """Apply a courier transition and its log together; the caller commits."""
    order_id = _required_text(order_id, "order_id")
    courier_user_id = _required_text(courier_user_id, "courier_user_id")
    with connection.begin_nested():
        order = connection.execute(
            select(orders).where(orders.c.id == order_id).with_for_update()
        ).mappings().one_or_none()
        if order is None:
            raise OrderNotFoundError("Order does not exist.")
        if order["courier_user_id"] != courier_user_id:
            raise OrderAccessDeniedError("Only the assigned courier can update this order.")
        reached = ["ACCEPTED", "PICKED_UP", "DELIVERED", "COMPLETING", "COMPLETED"]
        if order["status"] in reached[reached.index(next_status):]:
            return dict(order)
        if order["status"] != previous_status:
            raise OrderStateError(f"Order must be {previous_status} to move to {next_status}.")

        now = connection.execute(select(func.clock_timestamp())).scalar_one()
        updated = connection.execute(
            update(orders).where(orders.c.id == order_id)
            .values(status=next_status, updated_at=now).returning(orders)
        ).mappings().one()
        connection.execute(
            insert(order_log).values(
                order_id=order_id, actor_user_id=courier_user_id, action=action,
                outcome="SUCCEEDED", previous_status=previous_status,
                new_status=next_status, details={}, created_at=now,
            )
        )
        return dict(updated)


def mark_items_collected(
    connection: Connection,
    order_id: str,
    *,
    courier_user_id: str,
) -> dict[str, object]:
    """Let the assigned courier move ACCEPTED to PICKED_UP."""
    return _advance_courier_order(
        connection, order_id, courier_user_id,
        previous_status="ACCEPTED", next_status="PICKED_UP", action="MARK_ITEMS_COLLECTED",
    )


def mark_delivery_completed(
    connection: Connection,
    order_id: str,
    *,
    courier_user_id: str,
) -> dict[str, object]:
    """Let the assigned courier move PICKED_UP to DELIVERED, awaiting receipt."""
    return _advance_courier_order(
        connection, order_id, courier_user_id,
        previous_status="PICKED_UP", next_status="DELIVERED", action="MARK_DELIVERY_COMPLETED",
    )


def _change_requester_order(
    connection: Connection,
    order_id: str,
    requester_user_id: str,
    *,
    previous_status: str,
    next_status: str,
    completed_status: str,
    credit_operation: Literal["RELEASE", "TRANSFER"],
    action: str,
) -> dict[str, object]:
    """Atomically apply a requester transition, history and credit job.

    The caller commits. Retrying a pending or completed action adds no writes.
    Final status is set by the worker only after Credit Service acknowledges.
    """
    order_id = _required_text(order_id, "order_id")
    requester_user_id = _required_text(requester_user_id, "requester_user_id")
    with connection.begin_nested():
        order = connection.execute(
            select(orders).where(orders.c.id == order_id).with_for_update()
        ).mappings().one_or_none()
        if order is None:
            raise OrderNotFoundError("Order does not exist.")
        if order["requester_user_id"] != requester_user_id:
            raise OrderAccessDeniedError("Only the requester can update this order.")
        if order["status"] in (next_status, completed_status):
            return dict(order)
        if order["status"] != previous_status:
            raise OrderStateError(f"Order must be {previous_status} to move to {next_status}.")

        now = connection.execute(select(func.clock_timestamp())).scalar_one()
        updated = connection.execute(
            update(orders).where(orders.c.id == order_id)
            .values(status=next_status, updated_at=now).returning(orders)
        ).mappings().one()
        connection.execute(
            insert(order_log).values(
                order_id=order_id, actor_user_id=requester_user_id, action=action,
                outcome="SUCCEEDED", previous_status=previous_status,
                new_status=next_status, details={}, created_at=now,
            )
        )
        connection.execute(
            insert(credit_jobs).values(
                order_id=order_id, operation=credit_operation, attempts=0,
                next_attempt_at=now, created_at=now,
            )
        )
        return dict(updated)


def confirm_order_receipt(
    connection: Connection,
    order_id: str,
    *,
    requester_user_id: str,
) -> dict[str, object]:
    """Move the requester's DELIVERED order to COMPLETING and queue TRANSFER.

    Use the persisted courier ID and amount; retries must not queue extra jobs.
    """

    return _change_requester_order(
        connection, order_id, requester_user_id,
        previous_status="DELIVERED", next_status="COMPLETING",
        completed_status="COMPLETED", credit_operation="TRANSFER",
        action="CONFIRM_ORDER_RECEIPT",
    )


def cancel_open_order(
    connection: Connection,
    order_id: str,
    *,
    requester_user_id: str,
) -> dict[str, object]:
    """Move the requester's OPEN order to CANCELLING and queue one RELEASE."""
    return _change_requester_order(
        connection, order_id, requester_user_id,
        previous_status="OPEN", next_status="CANCELLING",
        completed_status="CANCELLED", credit_operation="RELEASE",
        action="CANCEL_ORDER",
    )


def get_order_history(
    connection: Connection,
    order_id: str,
    *,
    viewer_user_id: str,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, object]:
    """Read chronological history for the requester or assigned courier."""
    order_id = _required_text(order_id, "order_id")
    viewer_user_id = _required_text(viewer_user_id, "viewer_user_id")
    order = connection.execute(
        select(orders.c.requester_user_id, orders.c.courier_user_id)
        .where(orders.c.id == order_id)
    ).mappings().one_or_none()
    if order is None:
        raise OrderNotFoundError("Order does not exist.")
    if viewer_user_id not in (order["requester_user_id"], order["courier_user_id"]):
        raise OrderAccessDeniedError(
            "Only the requester or assigned courier can read order history."
        )

    return _page(connection,
        select(order_log)
        .where(order_log.c.order_id == order_id)
        .order_by(order_log.c.created_at.asc(), order_log.c.id.asc()), page, page_size,
    )


def expire_open_orders(
    connection: Connection,
    *,
    now: datetime,
    batch_size: int = 100,
) -> list[dict[str, object]]:
    """Atomically move due OPEN orders to EXPIRING and queue RELEASE jobs.

    Use now as the expiry cutoff. Skip rows locked by acceptance, cancellation
    or another expiry worker. The caller commits the batch; the credit worker
    marks orders EXPIRED only after release succeeds.
    """
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")

    with connection.begin_nested():
        order_ids = connection.execute(
            select(orders.c.id)
            .where(
                orders.c.status == "OPEN",
                orders.c.courier_user_id.is_(None),
                orders.c.expires_at <= now,
            )
            .order_by(orders.c.expires_at.asc(), orders.c.id.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        ).scalars().all()
        if not order_ids:
            return []

        changed_at = connection.execute(select(func.clock_timestamp())).scalar_one()
        expired = connection.execute(
            update(orders).where(orders.c.id.in_(order_ids))
            .values(status="EXPIRING", updated_at=changed_at).returning(orders)
        ).mappings().all()
        connection.execute(
            insert(order_log),
            [
                {
                    "order_id": order_id, "actor_user_id": None,
                    "action": "EXPIRE_ORDER", "outcome": "SUCCEEDED",
                    "previous_status": "OPEN", "new_status": "EXPIRING",
                    "details": {}, "created_at": changed_at,
                }
                for order_id in order_ids
            ],
        )
        connection.execute(
            insert(credit_jobs),
            [
                {
                    "order_id": order_id, "operation": "RELEASE", "attempts": 0,
                    "next_attempt_at": changed_at, "created_at": changed_at,
                }
                for order_id in order_ids
            ],
        )
        by_id = {row["id"]: dict(row) for row in expired}
        return [by_id[order_id] for order_id in order_ids]


def get_pending_credit_jobs(
    connection: Connection,
    *,
    now: datetime,
    batch_size: int = 100,
) -> list[dict[str, object]]:
    """Read due unfinished jobs with order IDs, parties, amounts and operations.

    Lock the orders until the caller's transaction ends. Workers must send and
    acknowledge each job within that transaction, using stable idempotency keys.
    """
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")
    rows = connection.execute(
        select(
            credit_jobs, orders.c.requester_user_id, orders.c.courier_user_id,
            orders.c.credit_amount, orders.c.status.label("order_status"),
        )
        .join(orders, orders.c.id == credit_jobs.c.order_id)
        .where(credit_jobs.c.completed_at.is_(None), credit_jobs.c.next_attempt_at <= now)
        .order_by(credit_jobs.c.next_attempt_at, credit_jobs.c.created_at, credit_jobs.c.id)
        .limit(batch_size)
        .with_for_update(of=orders, skip_locked=True)
    ).mappings().all()
    return [dict(row) for row in rows]


def _finish_credit_job(
    connection: Connection,
    job_id: str,
    finished_at: datetime,
    error_code: str | None = None,
) -> dict[str, object]:
    """Finish a credit action and its order atomically; the caller commits."""
    job_id = _required_text(job_id, "job_id")
    if not isinstance(finished_at, datetime) or finished_at.utcoffset() is None:
        raise ValueError("finished_at must be a timezone-aware datetime")
    if error_code is not None:
        error_code = _required_text(error_code, "error_code")
        if len(error_code) > 100:
            raise ValueError("error_code must be at most 100 characters")

    transitions = {
        ("RESERVE", "RESERVING"): "OPEN",
        ("RELEASE", "CANCELLING"): "CANCELLED",
        ("RELEASE", "EXPIRING"): "EXPIRED",
        ("TRANSFER", "COMPLETING"): "COMPLETED",
    }
    with connection.begin_nested():
        job = connection.execute(
            select(credit_jobs).where(credit_jobs.c.id == job_id)
        ).mappings().one_or_none()
        if job is None:
            raise LookupError("Credit job does not exist.")
        order = connection.execute(
            select(orders).where(orders.c.id == job["order_id"]).with_for_update()
        ).mappings().one()
        # Always lock order before job, matching the worker and API operations.
        job = connection.execute(
            select(credit_jobs).where(credit_jobs.c.id == job_id).with_for_update()
        ).mappings().one()
        if error_code is not None and job["operation"] != "RESERVE":
            raise OrderStateError("Only RESERVE jobs can be definitively rejected.")
        if job["completed_at"] is not None:
            if (error_code is None) != (job["last_error_code"] is None):
                raise OrderStateError("Credit job already finished with a different outcome.")
            return dict(order)
        next_status = transitions.get((job["operation"], order["status"]))
        if next_status is None or (error_code is not None and order["status"] != "RESERVING"):
            raise OrderStateError("Credit job does not match the pending order state.")
        if finished_at < max(job["created_at"], order["updated_at"]):
            raise ValueError("finished_at cannot precede the job or latest order update")
        next_status = "REJECTED" if error_code is not None else next_status
        if next_status == "OPEN" and order["expires_at"] <= finished_at:
            # A delayed reservation must never publish an already-expired order.
            next_status = "EXPIRING"
            connection.execute(insert(credit_jobs).values(
                order_id=order["id"], operation="RELEASE", attempts=0,
                next_attempt_at=finished_at, created_at=finished_at,
            ))

        connection.execute(
            update(credit_jobs).where(credit_jobs.c.id == job_id).values(
                completed_at=finished_at, last_error_code=error_code,
                attempts=credit_jobs.c.attempts + 1,
            )
        )
        updated = connection.execute(
            update(orders).where(orders.c.id == order["id"])
            .values(status=next_status, updated_at=finished_at).returning(orders)
        ).mappings().one()
        connection.execute(
            insert(order_log).values(
                order_id=order["id"], actor_user_id=None,
                action=f"CREDIT_{job['operation']}",
                outcome="REJECTED" if error_code is not None else "SUCCEEDED",
                previous_status=order["status"], new_status=next_status,
                details={"job_id": job_id, "error_code": error_code}, created_at=finished_at,
            )
        )
        return dict(updated)


def complete_credit_job(
    connection: Connection,
    job_id: str,
    *,
    completed_at: datetime,
) -> dict[str, object]:
    """After confirmed credit success, finish the job, order transition and log.

    RESERVE makes OPEN (or EXPIRING if already due); RELEASE makes CANCELLED or
    EXPIRED; TRANSFER makes COMPLETED. Repeated completion is harmless.
    """
    return _finish_credit_job(connection, job_id, completed_at)


def reschedule_credit_job(
    connection: Connection,
    job_id: str,
    *,
    next_attempt_at: datetime,
    last_error_code: str,
) -> None:
    """Record a failed attempt and schedule retry, preserving pending order state."""
    job_id = _required_text(job_id, "job_id")
    last_error_code = _required_text(last_error_code, "last_error_code")
    if len(last_error_code) > 100:
        raise ValueError("last_error_code must be at most 100 characters")
    if not isinstance(next_attempt_at, datetime) or next_attempt_at.utcoffset() is None:
        raise ValueError("next_attempt_at must be a timezone-aware datetime")

    with connection.begin_nested():
        job = connection.execute(
            select(credit_jobs).where(credit_jobs.c.id == job_id).with_for_update()
        ).mappings().one_or_none()
        if job is None:
            raise LookupError("Credit job does not exist.")
        if job["completed_at"] is not None:
            return
        if next_attempt_at < job["created_at"]:
            raise ValueError("next_attempt_at cannot precede job creation")
        connection.execute(
            update(credit_jobs).where(credit_jobs.c.id == job_id).values(
                attempts=credit_jobs.c.attempts + 1,
                next_attempt_at=next_attempt_at, last_error_code=last_error_code,
            )
        )


def reject_order_reservation(
    connection: Connection,
    job_id: str,
    *,
    rejected_at: datetime,
    error_code: str,
) -> dict[str, object]:
    """Finish a definitively rejected RESERVE job and mark its order REJECTED.

    Uncertain outcomes and temporary failures must be reconciled/retried instead.
    """
    return _finish_credit_job(connection, job_id, rejected_at, error_code)
