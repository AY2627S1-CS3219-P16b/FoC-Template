"""Admin order visibility, filtering, pagination and endpoint access checks."""

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from app.auth import CurrentUser, current_user
from app.main import create_app
from app.order_queries import list_admin_orders, list_orders
from app.schema import orders


class AdminOrderQueryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        # Only the order table is needed; no PostgreSQL worker/log operations.
        orders.create(self.engine)
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            for index, (requester, status, courier) in enumerate([
                ("requester-1", "OPEN", None),
                ("requester-1", "ACCEPTED", "courier-1"),
                ("requester-2", "COMPLETED", "courier-2"),
            ]):
                connection.execute(insert(orders).values(
                    id=str(index), requester_user_id=requester,
                    courier_user_id=courier, status=status, supplier_id="supplier-1",
                    supplier_name="Store", pickup_location="Store entrance",
                    item_description="Lunch", delivery_location="Library",
                    credit_amount=2, idempotency_key=str(index),
                    created_at=now - timedelta(days=2),
                    updated_at=now - timedelta(days=1),
                    expires_at=now - timedelta(hours=1),
                ))

    def test_all_statuses_and_couriers_including_expired_open_orders(self):
        with self.engine.connect() as connection:
            result = list_admin_orders(connection)
        self.assertEqual(result["total"], 3)
        self.assertEqual([row["id"] for row in result["items"]], ["2", "1", "0"])
        self.assertEqual(result["items"][0]["courier_user_id"], "courier-2")

    def test_requester_status_and_pagination(self):
        with self.engine.connect() as connection:
            result = list_admin_orders(connection, requester_user_id="requester-1",
                                       page=2, page_size=1)
            self.assertEqual(result["total"], 2)
            self.assertEqual(result["total_pages"], 2)
            self.assertEqual(result["items"][0]["id"], "0")
            result = list_admin_orders(connection, requester_user_id="requester-1",
                                       status="ACCEPTED")
            self.assertEqual([row["id"] for row in result["items"]], ["1"])
            self.assertEqual(list_admin_orders(connection, requester_user_id="missing")["total"], 0)

    def test_ordinary_users_still_cannot_list_other_users_closed_orders(self):
        with self.engine.connect() as connection:
            self.assertEqual(list_orders(connection, viewer_user_id="outsider",
                                         status="COMPLETED")["total"], 0)
            self.assertEqual(list_orders(connection, viewer_user_id="courier-2",
                                         status="COMPLETED")["total"], 1)


class AdminOrderEndpointTests(unittest.TestCase):
    def setUp(self):
        self.engine = MagicMock()
        with patch("app.main.create_database_engine", return_value=self.engine), \
                patch("app.main.load_jwt_public_key"):
            self.app = create_app()
        self.app.state.database = self.engine
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def caller(self, auth_role):
        self.app.dependency_overrides[current_user] = lambda: CurrentUser(
            id="viewer", auth_role=auth_role, active_role_mode="REQUESTER",
            account_status="ACTIVE",
        )

    def test_anonymous_and_non_admin_are_denied_before_querying(self):
        self.assertEqual(self.client.get("/api/v1/orders/admin").status_code, 401)
        self.caller("USER")
        self.assertEqual(self.client.get("/api/v1/orders/admin").status_code, 403)
        self.engine.connect.assert_not_called()

    def test_admin_filters_are_forwarded_and_validated(self):
        self.caller("ADMIN")
        with patch("app.main.queries.list_admin_orders", return_value={
            "items": [], "page": 2, "page_size": 5, "total": 0, "total_pages": 0,
        }) as query:
            response = self.client.get("/api/v1/orders/admin", params={
                "requester_user_id": "requester-1", "status": "COMPLETED",
                "page": 2, "page_size": 5,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(query.call_args.kwargs, {
                "requester_user_id": "requester-1", "status": "COMPLETED",
                "page": 2, "page_size": 5,
            })
        for params in ({"status": "INVALID"}, {"page": 0}, {"page_size": 101}):
            self.assertEqual(self.client.get("/api/v1/orders/admin", params=params).status_code, 422)
