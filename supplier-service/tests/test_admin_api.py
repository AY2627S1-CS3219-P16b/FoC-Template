"""Who may change supplier records, and how refusals are reported.

The query layer is mocked so these run without PostgreSQL: what is under test
is the access rules and the mapping from a failed write to a status code, not
the SQL. Storage behaviour is covered by the live database tests.
"""

import base64
from datetime import time
import json
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.admin_queries import (
    DuplicatePlaceError,
    DuplicateSupplierError,
    NoChangeError,
    UnknownPlaceError,
)
from app.main import create_app


REASON = {"X-Admin-Reason": "stall closed for renovation"}


def supplier_row(**overrides):
    """A row shaped like get_supplier's, which nests the place columns."""
    return {
        "id": uuid4(), "name": "Test Cafe", "supplier_type": "FOOD_BEVERAGE",
        "tags": ["coffee"], "floor": None, "location_description": None,
        "latitude": None, "longitude": None,
        # Not null: the columns are required, so no row can come back without them.
        "opening_time": time(8, 0), "closing_time": time(18, 0),
        "image_url": None, "pickup_instructions": None,
        "is_active": True, "place_id": uuid4(), "place_name": "COM2",
        "place_parent_id": None, "place_parent_name": None, **overrides,
    }


class AdminEndpointTests(unittest.TestCase):
    def setUp(self):
        self.user_id = str(uuid4())
        self.profile = dict(id=self.user_id, auth_role="ADMIN",
                            active_role_mode="REQUESTER", account_status="ACTIVE")
        self.engine = MagicMock()
        with patch("app.main.create_database_engine", return_value=self.engine):
            self.app = create_app()
        self.upstream = httpx.Client(
            base_url="http://user-service",
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=self.profile)),
        )
        self.app.state.user_client = self.upstream
        self.app.state.database = self.engine
        self.client = TestClient(self.app)
        self.place_id = str(uuid4())
        self.supplier_id = str(uuid4())
        self.body = {"name": "Test Cafe", "supplier_type": "FOOD_BEVERAGE",
                     "place_id": self.place_id,
                     "opening_time": "08:00", "closing_time": "18:00"}
        # Creating a record needs no reason; changing or hiding one does.
        self.creates = [
            ("post", "/api/v1/suppliers", self.body),
            ("post", "/api/v1/places", {"name": "Test Kiosk"}),
        ]
        self.changes = [
            ("patch", f"/api/v1/suppliers/{self.supplier_id}", {"name": "Renamed"}),
            ("delete", f"/api/v1/suppliers/{self.supplier_id}", None),
        ]
        # Every admin route, so a new one cannot be added without a rule.
        self.writes = self.creates + self.changes

    def tearDown(self):
        self.client.close()
        self.upstream.close()

    def token(self):
        payload = {"sub": self.user_id}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        return {"Authorization": f"Bearer header.{encoded}.signature"}

    def call(self, method, path, body, **headers):
        send = getattr(self.client, method)
        return send(path, headers={**self.token(), **headers},
                    **({} if body is None else {"json": body}))

    def test_non_admin_is_refused_on_every_write(self):
        self.profile["auth_role"] = "USER"
        for method, path, body in self.writes + [("get", "/api/v1/supplier-changes", None)]:
            response = self.call(method, path, body, **REASON)
            self.assertEqual(response.status_code, 403, path)
            self.assertEqual(response.json()["detail"], "Admin access is required.")
        self.engine.begin.assert_not_called()

    def test_unauthenticated_is_refused_before_the_role_check(self):
        for method, path, body in self.writes:
            send = getattr(self.client, method)
            response = send(path, headers=REASON, **({} if body is None else {"json": body}))
            self.assertEqual(response.status_code, 401, path)
        self.engine.begin.assert_not_called()

    def test_reason_header_is_required_to_change_but_not_to_create(self):
        for method, path, body in self.changes:
            self.assertEqual(self.call(method, path, body).status_code, 422, path)
            self.assertEqual(
                self.call(method, path, body, **{"X-Admin-Reason": "   "}).status_code,
                422, path,
            )
        self.engine.begin.assert_not_called()

        # Creating without the header reaches the query layer, matching User
        # Service, where registering an account needs no reason.
        with patch("app.main.create_supplier", return_value=supplier_row()) as create:
            self.assertEqual(
                self.call("post", "/api/v1/suppliers", self.body).status_code, 201)
        self.assertNotIn("reason", create.call_args.kwargs)

    def test_admin_can_create_and_the_actor_is_recorded(self):
        row = supplier_row()
        with patch("app.main.create_supplier", return_value=row) as create:
            response = self.call("post", "/api/v1/suppliers", self.body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["place"]["name"], "COM2")
        self.assertEqual(str(create.call_args.kwargs["actor_id"]), self.user_id)

    def test_real_floor_labels_are_accepted(self):
        row = supplier_row()
        for floor in ("B1", "G", "1", "13", None):
            with patch("app.main.create_supplier", return_value=row):
                response = self.call(
                    "post", "/api/v1/suppliers", {**self.body, "floor": floor})
            self.assertEqual(response.status_code, 201, floor)

    def test_the_reason_reaches_the_audit_log_on_a_change(self):
        with patch("app.main.update_supplier", return_value=supplier_row()) as edit:
            self.call("patch", f"/api/v1/suppliers/{self.supplier_id}",
                      {"name": "Renamed"}, **REASON)
        self.assertEqual(edit.call_args.kwargs["reason"], REASON["X-Admin-Reason"])
        self.assertEqual(str(edit.call_args.kwargs["actor_id"]), self.user_id)

    def test_failed_writes_map_to_status_codes(self):
        cases = [
            ("app.main.create_supplier", "post", "/api/v1/suppliers", self.body,
             [(UnknownPlaceError, 404), (DuplicateSupplierError, 409)]),
            ("app.main.update_supplier", "patch", f"/api/v1/suppliers/{self.supplier_id}",
             {"name": "Renamed"},
             [(UnknownPlaceError, 404), (DuplicateSupplierError, 409), (NoChangeError, 409)]),
            ("app.main.deactivate_supplier", "delete",
             f"/api/v1/suppliers/{self.supplier_id}", None, [(NoChangeError, 409)]),
            ("app.main.create_place", "post", "/api/v1/places", {"name": "Test Kiosk"},
             [(UnknownPlaceError, 404), (DuplicatePlaceError, 409)]),
        ]
        for target, method, path, body, outcomes in cases:
            for error, expected in outcomes:
                with patch(target, side_effect=error):
                    response = self.call(method, path, body, **REASON)
                self.assertEqual(response.status_code, expected, f"{path} {error.__name__}")

    def test_missing_supplier_returns_not_found(self):
        for target, method, body in (("app.main.update_supplier", "patch", {"name": "X"}),
                                     ("app.main.deactivate_supplier", "delete", None)):
            with patch(target, return_value=None):
                response = self.call(method, f"/api/v1/suppliers/{self.supplier_id}",
                                     body, **REASON)
            self.assertEqual(response.status_code, 404)

    def test_invalid_input_is_refused_before_the_database(self):
        cases = [
            ("post", "/api/v1/suppliers", {**self.body, "supplier_type": "COFFEE"}),
            ("post", "/api/v1/suppliers", {**self.body, "name": "   "}),
            ("post", "/api/v1/suppliers", {**self.body, "latitude": 91}),
            ("post", "/api/v1/suppliers", {**self.body, "place_id": "not-a-uuid"}),
            ("post", "/api/v1/suppliers", {**self.body, "tags": ["ok", "!!"]}),
            # A floor is a short label like B1 or 13, not free text.
            ("post", "/api/v1/suppliers", {**self.body, "floor": "Level 1"}),
            ("post", "/api/v1/suppliers", {**self.body, "floor": "B-1"}),
            # Hours are required, so an order can tell whether a supplier is open.
            ("post", "/api/v1/suppliers", {k: v for k, v in self.body.items()
                                           if k != "opening_time"}),
            ("post", "/api/v1/suppliers", {**self.body, "closing_time": "25:00"}),
            ("patch", f"/api/v1/suppliers/{self.supplier_id}", {"opening_time": None}),
            # Required columns cannot be blanked, and a no-op is not a change.
            ("patch", f"/api/v1/suppliers/{self.supplier_id}", {"name": None}),
            ("patch", f"/api/v1/suppliers/{self.supplier_id}", {"is_active": None}),
            ("patch", f"/api/v1/suppliers/{self.supplier_id}", {}),
            ("post", "/api/v1/places", {"name": "  "}),
        ]
        for method, path, body in cases:
            response = self.call(method, path, body, **REASON)
            self.assertEqual(response.status_code, 422, f"{path} {body}")
        self.engine.begin.assert_not_called()

    def test_tags_are_normalized_before_storage(self):
        row = supplier_row()
        with patch("app.main.create_supplier", return_value=row) as create:
            self.call("post", "/api/v1/suppliers",
                      {**self.body, "tags": ["Coffee", " COFFEE ", "Halal"]}, **REASON)
        self.assertEqual(create.call_args.kwargs["values"]["tags"], ["coffee", "halal"])

    def test_update_sends_only_the_supplied_fields(self):
        row = supplier_row(name="Renamed")
        with patch("app.main.update_supplier", return_value=row) as edit:
            self.call("patch", f"/api/v1/suppliers/{self.supplier_id}",
                      {"name": "Renamed"}, **REASON)
        self.assertEqual(edit.call_args.kwargs["changes"], {"name": "Renamed"})
