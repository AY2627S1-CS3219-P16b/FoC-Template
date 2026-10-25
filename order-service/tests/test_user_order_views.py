"""User order views filter before pagination without changing ownership rules."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from app.auth import CurrentUser, current_user
from app.main import create_app
from app.order_queries import get_user_orders
from app.schema import ORDER_STATUSES, orders


class UserOrderViewTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        orders.create(self.engine)
        now = datetime.now(timezone.utc)
        with self.engine.begin() as connection:
            for owner in ("mine", "other"):
                for index, status in enumerate(ORDER_STATUSES):
                    connection.execute(insert(orders).values(
                        id=f"{owner}-{status}", requester_user_id=owner,
                        courier_user_id=f"courier-{owner}" if status in {"ACCEPTED", "PICKED_UP", "DELIVERED", "COMPLETING", "COMPLETED"} else None, status=status,
                        supplier_id="store", supplier_name="Store", pickup_location="Entrance",
                        item_description="Lunch", delivery_location="Library", credit_amount=1,
                        idempotency_key=f"{owner}-{status}", created_at=now + timedelta(seconds=index),
                        updated_at=now + timedelta(minutes=1), expires_at=now + timedelta(hours=1),
                    ))

    def test_active_includes_processing_and_past_contains_only_finished_states(self):
        past = {"COMPLETED", "CANCELLED", "EXPIRED", "REJECTED"}
        with self.engine.connect() as connection:
            for role, user in (("requester", "mine"), ("courier", "courier-mine")):
                active = get_user_orders(connection, user, role=role, view="active")
                history = get_user_orders(connection, user, role=role, view="past")
                expected = set(ORDER_STATUSES) if role == "requester" else {"ACCEPTED", "PICKED_UP", "DELIVERED", "COMPLETING", "COMPLETED"}
                self.assertEqual({row["status"] for row in active["items"]}, expected - past)
                self.assertEqual({row["status"] for row in history["items"]}, expected & past)
                self.assertTrue(all(row["requester_user_id"] == "mine" for row in active["items"] + history["items"]))
                self.assertEqual(get_user_orders(connection, user, role=role)["total"], len(expected))

    def test_filters_apply_before_pagination_and_combine_with_status(self):
        with self.engine.connect() as connection:
            pages = [get_user_orders(connection, "mine", role="requester", view="past", page=page, page_size=2) for page in (1, 2)]
            self.assertEqual([page["total"] for page in pages], [4, 4])
            self.assertEqual([page["total_pages"] for page in pages], [2, 2])
            self.assertEqual(len({row["id"] for page in pages for row in page["items"]}), 4)
            self.assertEqual(get_user_orders(connection, "mine", role="requester", view="active", status="COMPLETED")["total"], 0)
            self.assertEqual(get_user_orders(connection, "mine", role="requester", view="past", status="COMPLETED")["total"], 1)
            with self.assertRaises(ValueError):
                get_user_orders(connection, "mine", role="requester", view="invalid")

    def test_endpoint_validates_and_forwards_view_with_authenticated_user(self):
        engine = MagicMock()
        with patch("app.main.create_database_engine", return_value=engine), patch("app.main.load_jwt_public_key"):
            app = create_app()
        app.state.database = engine
        app.dependency_overrides[current_user] = lambda: CurrentUser(id="mine", auth_role="USER", active_role_mode="REQUESTER", account_status="ACTIVE")
        with TestClient(app) as client, patch("app.main.queries.get_user_orders", return_value={"items": [], "page": 2, "page_size": 10, "total": 0, "total_pages": 0}) as query:
            response = client.get("/api/v1/orders/me", params={"role": "requester", "view": "past", "page": 2, "page_size": 10})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(query.call_args.args[1], "mine")
            self.assertEqual(query.call_args.kwargs, {"role": "requester", "view": "past", "status": None, "page": 2, "page_size": 10})
            query.reset_mock()
            self.assertEqual(client.get("/api/v1/orders/me?role=requester&view=invalid").status_code, 422)
            query.assert_not_called()
