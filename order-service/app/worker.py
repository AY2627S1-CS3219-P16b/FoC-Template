"""Durable credit delivery and order expiry: python -m app.worker."""

import logging
import os
import signal
from datetime import timedelta
from http.client import HTTPException as HTTPProtocolError
from threading import Event
from urllib.error import HTTPError

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from . import order_queries as queries
from .database import create_database_engine
from .service_clients import CreditClient, InsufficientCredits

logger = logging.getLogger(__name__)


def database_now(connection):
    return connection.execute(select(func.clock_timestamp())).scalar_one()


def deliver_one(engine, client: CreditClient) -> bool:
    """Hold the order lock through delivery and acknowledgement, one job at a time."""
    with engine.begin() as connection:
        jobs = queries.get_pending_credit_jobs(connection, now=database_now(connection), batch_size=1)
        if not jobs:
            return False
        job = jobs[0]
        try:
            client.apply(job)
        except InsufficientCredits:
            queries.reject_order_reservation(
                connection, job["id"], rejected_at=database_now(connection),
                error_code="INSUFFICIENT_CREDITS",
            )
            logger.info("credit rejected job=%s order=%s", job["id"], job["order_id"])
        except (OSError, ValueError, RuntimeError, HTTPProtocolError) as error:
            # Do not expose credentials or discard jobs on persistent errors.
            code = f"HTTP_{error.code}" if isinstance(error, HTTPError) else type(error).__name__
            delay = min(300, 2 ** min(job["attempts"] + 1, 8))
            queries.reschedule_credit_job(
                connection, job["id"], last_error_code=code,
                next_attempt_at=database_now(connection) + timedelta(seconds=delay),
            )
            logger.warning("credit retry job=%s order=%s attempt=%s error=%s",
                           job["id"], job["order_id"], job["attempts"] + 1, code)
        else:
            queries.complete_credit_job(connection, job["id"], completed_at=database_now(connection))
            logger.info("credit succeeded job=%s order=%s operation=%s",
                        job["id"], job["order_id"], job["operation"])
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    engine = create_database_engine()
    client = CreditClient(os.getenv("CREDIT_SERVICE_URL", "http://localhost:8002"),
                          os.environ["ORDER_SERVICE_KEY"])
    stop = Event()
    for event in (signal.SIGTERM, signal.SIGINT):
        signal.signal(event, lambda *_: stop.set())
    try:
        while not stop.is_set():
            delivered = False
            try:
                with engine.begin() as connection:
                    queries.expire_open_orders(connection, now=database_now(connection))
                delivered = deliver_one(engine, client)
            except SQLAlchemyError as error:
                logger.warning("Order queue unavailable; retrying error=%s", type(error).__name__)
            stop.wait(0 if delivered else 1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
