"""Deduplicate registration messages and grant the allocation atomically."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .api_schemas import UserRegisteredEvent
from .credit_queries import ensure_account
from .schema import processed_events


def consume_registration(connection, event: UserRegisteredEvent):
    created = connection.execute(
        insert(processed_events).values(event_id=event.event_id, user_id=event.user_id)
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(processed_events.c.event_id)
    ).scalar_one_or_none()
    if created is None:
        existing = connection.execute(select(processed_events).where(
            processed_events.c.event_id == event.event_id)).mappings().one()
        if existing["user_id"] != event.user_id:
            raise HTTPException(409, "Event ID was already used for a different user.")
    # Account and deduplication marker commit together. Different event IDs for
    # the same user still cannot grant another allocation.
    account = ensure_account(connection, event.user_id)
    return {"duplicate": created is None, "user_id": account["user_id"]}

