"""PostgreSQL integration tests for atomic, idempotent order creation.

Set ORDER_TEST_DATABASE_URL to a disposable PostgreSQL database. Each test uses
its own schema; existing application tables are never touched.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from threading import Barrier
import unittest
from uuid import UUID, uuid4

from sqlalchemy import create_engine, event, func, select, text, update

from app.order_queries import OrderIdempotencyConflict, create_order
from app.schema import credit_jobs, metadata, order_log, orders


@unittest.skipUnless(os.getenv("ORDER_TEST_DATABASE_URL"), "Set ORDER_TEST_DATABASE_URL")
class CreateOrderTests(unittest.TestCase):
    def setUp(self):
        self.schema = "test_orders_" + uuid4().hex
        url = os.environ["ORDER_TEST_DATABASE_URL"]
        self.admin = create_engine(url)
        with self.admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = create_engine(url, connect_args={"options": f"-csearch_path={self.schema}"})
        self.addCleanup(self.cleanup_database)
        metadata.create_all(self.engine)
        self.fields = dict(
            requester_user_id="requester-1", supplier_id="supplier-1",
            supplier_name="Campus Cafe", pickup_location="COM1",
            item_description="Coffee", delivery_location="COM2",
            credit_amount=3, expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            idempotency_key="request-1", delivery_instructions="At the lobby",
        )

    def cleanup_database(self):
        self.engine.dispose()
        with self.admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        self.admin.dispose()

    def create(self, **changes):
        with self.engine.begin() as connection:
            return create_order(connection, **{**self.fields, **changes})

    def counts(self):
        with self.engine.connect() as connection:
            return tuple(connection.scalar(select(func.count()).select_from(table))
                         for table in (orders, order_log, credit_jobs))

    def test_create_persists_order_history_and_credit_job(self):
        order = self.create()
        UUID(order["id"])
        self.assertEqual(order["status"], "RESERVING")
        self.assertIsNone(order["courier_user_id"])
        self.assertEqual(self.counts(), (1, 1, 1))
        with self.engine.connect() as connection:
            log = connection.execute(select(order_log)).mappings().one()
            job = connection.execute(select(credit_jobs)).mappings().one()
        self.assertEqual(log["order_id"], order["id"])
        self.assertEqual(log["actor_user_id"], self.fields["requester_user_id"])
        self.assertEqual(log["new_status"], "RESERVING")
        self.assertEqual(job["order_id"], order["id"])
        self.assertEqual(job["operation"], "RESERVE")
        self.assertEqual(job["attempts"], 0)
        self.assertIsNone(job["completed_at"])

    def test_identical_retry_returns_current_order_without_new_writes(self):
        first = self.create()
        with self.engine.begin() as connection:
            connection.execute(update(orders).values(status="OPEN"))
        retry = self.create()
        self.assertEqual(retry["id"], first["id"])
        self.assertEqual(retry["status"], "OPEN")
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_changed_payload_conflicts(self):
        self.create()
        for changes in ({"credit_amount": 4}, {"item_description": "Tea"},
                        {"delivery_location": "Library"}, {"delivery_instructions": None},
                        {"expires_at": self.fields["expires_at"] + timedelta(minutes=1)}):
            with self.subTest(changes=changes), self.assertRaises(OrderIdempotencyConflict):
                self.create(**changes)
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_key_is_scoped_to_requester(self):
        first = self.create()
        second = self.create(requester_user_id="requester-2")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(self.counts(), (2, 2, 2))

    def test_normalizes_whitespace_and_optional_instructions(self):
        first = self.create(item_description=" Coffee ", delivery_instructions="  ")
        retry = self.create(delivery_instructions=None)
        self.assertEqual(first["id"], retry["id"])
        self.assertEqual(first["item_description"], "Coffee")
        self.assertIsNone(first["delivery_instructions"])

    def test_rejects_invalid_input_without_writes(self):
        cases = [
            {"credit_amount": value} for value in (0, -1, True, 1.5, "3", 2147483648)
        ] + [
            {"expires_at": datetime.now()},
            {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)},
            {"requester_user_id": None}, {"supplier_name": " "},
            {"supplier_name": "a" * 201}, {"idempotency_key": "a" * 201},
            {"delivery_instructions": 123},
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.create(**changes)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_retry_after_expiry_still_returns_existing_order(self):
        self.create()
        # Put both stored and retried deadline in the past while preserving the
        # schema invariant that expiry follows creation.
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        with self.engine.begin() as connection:
            connection.execute(update(orders).values(
                expires_at=past, created_at=past - timedelta(hours=1),
            ))
        retry = self.create(expires_at=past)
        self.assertEqual(retry["expires_at"], past)
        self.assertEqual(self.counts(), (1, 1, 1))

    def test_caller_rollback_removes_all_writes(self):
        with self.engine.connect() as connection:
            transaction = connection.begin()
            create_order(connection, **self.fields)
            transaction.rollback()
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_job_failure_rolls_back_order_and_log_even_if_caught(self):
        def fail_job(connection, cursor, statement, parameters, context, executemany):
            if statement.startswith("INSERT INTO credit_jobs"):
                raise RuntimeError("Simulated job insert failure")

        event.listen(self.engine, "before_cursor_execute", fail_job)
        try:
            with self.engine.begin() as connection:
                with self.assertRaisesRegex(RuntimeError, "Simulated"):
                    create_order(connection, **self.fields)
        finally:
            event.remove(self.engine, "before_cursor_execute", fail_job)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_concurrent_retries_create_one_order(self):
        barrier = Barrier(2)

        def submit():
            barrier.wait(timeout=10)
            return self.create()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(results[0]["id"], results[1]["id"])
        self.assertEqual(self.counts(), (1, 1, 1))


if __name__ == "__main__":
    unittest.main()
