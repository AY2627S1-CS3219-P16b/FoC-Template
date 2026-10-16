"""Durable, at-least-once HTTP delivery of registration allocation messages.

Run independently: python -m app.credit_worker. No broker is required; the
transactional outbox is the persistent queue. Never delete unacknowledged rows.
"""
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json

from sqlalchemy import or_, select, update
from sqlalchemy.exc import SQLAlchemyError

from .database import Database, credit_outbox

logger = logging.getLogger(__name__)


def send_event(url, key, payload):
    request = Request(url.rstrip("/") + "/internal/events/user-registered",
                      data=json.dumps(payload).encode(), method="POST",
                      headers={"Content-Type": "application/json", "X-Service-Key": key})
    with urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError("Unexpected allocation response status")


def deliver_batch(database, url, key, limit=20):
    delivered = 0
    for _ in range(limit):
        now = datetime.now(timezone.utc)
        with database.engine.begin() as connection:
            # Keep the row locked through acknowledgement. If the worker dies
            # after Credit commits, this row is retried and Credit deduplicates.
            row = connection.execute(
                select(credit_outbox).where(
                    credit_outbox.c.delivered_at.is_(None),
                    or_(credit_outbox.c.next_attempt_at.is_(None),
                        credit_outbox.c.next_attempt_at <= now.isoformat()),
                ).order_by(credit_outbox.c.occurred_at, credit_outbox.c.event_id)
                .limit(1).with_for_update(skip_locked=True)
            ).mappings().one_or_none()
            if row is None:
                break
            attempts = row["attempts"] + 1
            payload = {"event_id": row["event_id"], "type": "user.registered.v1",
                       "user_id": row["user_id"], "occurred_at": row["occurred_at"]}
            try:
                send_event(url, key, payload)
            except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as error:
                # Log only type/status: exception text can contain credentials.
                logger.warning("allocation delivery failed event=%s attempt=%s error=%s status=%s",
                               row["event_id"], attempts, type(error).__name__, getattr(error, "code", None))
                changes = {"attempts": attempts, "next_attempt_at": (
                    now + timedelta(seconds=min(300, 2 ** min(attempts, 8)))).isoformat()}
            else:
                changes = {"attempts": attempts, "delivered_at": now.isoformat()}
                delivered += 1
                logger.info("allocation delivered event=%s attempt=%s", row["event_id"], attempts)
            connection.execute(update(credit_outbox).where(
                credit_outbox.c.event_id == row["event_id"]).values(**changes))
    return delivered


def main():
    logging.basicConfig(level=logging.INFO)
    database = Database(os.environ["DATABASE_URL"])
    url, key = os.environ["CREDIT_SERVICE_URL"], os.environ["USER_SERVICE_KEY"]
    try:
        while True:
            try:
                deliver_batch(database, url, key)
            except SQLAlchemyError:
                logger.warning("Allocation queue unavailable; retrying")
            time.sleep(1)
    finally:
        database.close()


if __name__ == "__main__":
    main()
