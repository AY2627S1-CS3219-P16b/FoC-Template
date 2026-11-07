"""Acceptance deadlines: at most an hour away, and before the store closes."""

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.auth import CurrentUser, current_user
from app.main import create_app
from app.order_queries import CLOSING_BUFFER, create_order
from app.service_clients import SupplierSnapshot, supplier_snapshot

CAMPUS = timezone(timedelta(hours=8))
NOW = datetime(2026, 11, 9, 20, 0, tzinfo=CAMPUS)
SUPPLIER_ID = "6f1c2a52-3a5e-4f43-9d5b-2b6c1c0f4e11"


def fake_connection():
    """Answer create_order's first queries: lock, no earlier retry, database time."""
    connection = MagicMock()
    no_retry = MagicMock()
    no_retry.mappings.return_value.one_or_none.return_value = None
    clock = MagicMock()
    clock.scalar_one.return_value = NOW
    connection.execute.side_effect = [MagicMock(), no_retry, clock] + [MagicMock() for _ in range(5)]
    return connection


def create(expires_at, closes_at=None):
    connection = fake_connection()
    create_order(
        connection, requester_user_id="requester", supplier_id=SUPPLIER_ID,
        supplier_name="Supersnacks", pickup_location="COM2", item_description="Chips",
        delivery_location="COM3 lobby", credit_amount=1, expires_at=expires_at,
        idempotency_key="key-1", supplier_closes_at=closes_at,
    )
    return connection


class DeadlineRuleTests(unittest.TestCase):
    def test_deadline_more_than_an_hour_away_is_refused(self):
        with self.assertRaisesRegex(ValueError, "at most 60 minutes"):
            create(NOW + timedelta(days=365))

    def test_an_hour_is_allowed_with_room_for_a_fast_device_clock(self):
        for minutes in (30, 60, 64):
            with self.subTest(minutes=minutes):
                # Reaching the insert means every deadline check passed.
                self.assertGreater(create(NOW + timedelta(minutes=minutes)).execute.call_count, 3)

    def test_deadline_must_leave_the_courier_time_before_closing(self):
        closes = NOW + timedelta(minutes=40)   # store shuts at 20:40
        with self.assertRaisesRegex(ValueError, "closes at 20:40.*by 20:30"):
            create(NOW + timedelta(minutes=35), closes)
        self.assertGreater(create(closes - CLOSING_BUFFER, closes).execute.call_count, 3)

    def test_a_store_that_never_closes_only_has_the_hour_limit(self):
        self.assertGreater(create(NOW + timedelta(minutes=60), None).execute.call_count, 3)


class SupplierClosingTimeTests(unittest.TestCase):
    def supplier(self, **overrides):
        return {"id": SUPPLIER_ID, "name": "Supersnacks", "place": {"name": "COM2"},
                "is_active": True, "is_open_now": True, **overrides}

    def test_closing_time_is_read_from_supplier_service(self):
        with patch("app.service_clients._request_json",
                   return_value=self.supplier(closes_at="2026-11-09T21:00:00+08:00")):
            snapshot = supplier_snapshot("http://supplier", SUPPLIER_ID, "Bearer t")
        self.assertEqual(snapshot.closes_at, datetime(2026, 11, 9, 21, 0, tzinfo=CAMPUS))

    def test_missing_or_null_closing_time_means_never_closes(self):
        for supplier in (self.supplier(), self.supplier(closes_at=None)):
            with self.subTest(supplier=supplier), \
                 patch("app.service_clients._request_json", return_value=supplier):
                self.assertIsNone(supplier_snapshot("http://supplier", SUPPLIER_ID, "t").closes_at)

    def test_endpoint_passes_the_closing_time_to_create_order(self):
        engine = MagicMock()
        engine.connect.return_value.__enter__.return_value.execute.return_value \
            .mappings.return_value.one_or_none.return_value = None
        with patch("app.main.create_database_engine", return_value=engine), \
             patch("app.main.load_jwt_public_key"):
            app = create_app()
        app.state.database = engine
        app.dependency_overrides[current_user] = lambda: CurrentUser(
            id="requester", auth_role="USER", active_role_mode="REQUESTER",
            account_status="ACTIVE")
        closes = datetime(2026, 11, 9, 21, 0, tzinfo=CAMPUS)
        body = {"supplier_id": SUPPLIER_ID, "item_description": "Chips",
                "delivery_location": "COM3 lobby", "credit_amount": 1,
                "expires_at": "2026-11-09T20:30:00+08:00"}
        with TestClient(app) as client, \
             patch("app.main.supplier_snapshot",
                   return_value=SupplierSnapshot("Supersnacks", "COM2", closes)), \
             patch("app.main.queries.create_order",
                   side_effect=ValueError("stop after the call")) as query:
            response = client.post("/api/v1/orders", json=body,
                                   headers={"Idempotency-Key": "k", "Authorization": "Bearer t"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(query.call_args.kwargs["supplier_closes_at"], closes)


if __name__ == "__main__":
    unittest.main()
