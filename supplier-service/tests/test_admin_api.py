"""Who may change supplier records, and how refusals are reported.

The query layer is mocked so these run without PostgreSQL: what is under test
is the access rules and the mapping from a failed write to a status code, not
the SQL. Storage behaviour is covered by the live database tests.
"""

from datetime import time
import io
import os
import tempfile
import time as time_module
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

import jwt
from PIL import Image
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat,
)
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
        "operating_days": ["MON", "TUE", "WED", "THU", "FRI"],
        "image_url": None, "pickup_instructions": None,
        "is_active": True, "place_id": uuid4(), "place_name": "COM2",
        "place_parent_id": None, "place_parent_name": None, **overrides,
    }


class AdminEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private_pem = cls.private_key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

    def setUp(self):
        self.user_id = str(uuid4())
        # Read by token() on every call, so mutating this mid-test (as the
        # non-admin test does) changes what the next signed token claims.
        self.profile = dict(id=self.user_id, auth_role="ADMIN",
                            active_role_mode="REQUESTER", account_status="ACTIVE")
        self.engine = MagicMock()
        # Uploads land in a throwaway folder, never the developer's uploads/.
        self.image_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.image_dir.cleanup)
        with patch("app.main.create_database_engine", return_value=self.engine), \
             patch("app.main.load_jwt_public_key", return_value=self.private_key.public_key()), \
             patch.dict(os.environ, {"SUPPLIER_IMAGE_DIR": self.image_dir.name}):
            self.app = create_app()
        self.app.state.jwt_public_key = self.private_key.public_key()
        self.app.state.database = self.engine
        self.client = TestClient(self.app)
        self.place_id = str(uuid4())
        self.supplier_id = str(uuid4())
        self.body = {"name": "Test Cafe", "supplier_type": "FOOD_BEVERAGE",
                     "place_id": self.place_id,
                     "opening_time": "08:00", "closing_time": "18:00",
                     "operating_days": ["MON", "TUE", "WED", "THU", "FRI"]}
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
        self.writes = self.creates + self.changes + [
            ("post", "/api/v1/supplier-images", None),
        ]

    def tearDown(self):
        self.client.close()

    def token(self):
        payload = {**self.profile, "sub": self.profile["id"],
                  "exp": int(time_module.time()) + 900}
        encoded = jwt.encode(payload, self.private_pem, algorithm="RS256")
        return {"Authorization": f"Bearer {encoded}"}

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
            # Operating days are required too, and must be real weekdays.
            ("post", "/api/v1/suppliers", {k: v for k, v in self.body.items()
                                           if k != "operating_days"}),
            ("post", "/api/v1/suppliers", {**self.body, "operating_days": []}),
            ("post", "/api/v1/suppliers", {**self.body, "operating_days": ["FUNDAY"]}),
            ("patch", f"/api/v1/suppliers/{self.supplier_id}", {"operating_days": None}),
            ("patch", f"/api/v1/suppliers/{self.supplier_id}", {"operating_days": []}),
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

    def test_operating_days_are_normalized_before_storage(self):
        row = supplier_row()
        with patch("app.main.create_supplier", return_value=row) as create:
            self.call("post", "/api/v1/suppliers",
                      {**self.body, "operating_days": ["fri", "MON", " wed ", "MON"]})
        self.assertEqual(create.call_args.kwargs["values"]["operating_days"],
                         ["MON", "WED", "FRI"])

    def test_response_reports_days_and_whether_open_now(self):
        with patch("app.main.create_supplier", return_value=supplier_row()):
            body = self.call("post", "/api/v1/suppliers", self.body).json()
        self.assertEqual(body["operating_days"], ["MON", "TUE", "WED", "THU", "FRI"])
        self.assertIsInstance(body["is_open_now"], bool)

    def test_removing_a_photo_is_an_audited_change_with_a_reason(self):
        path = f"/api/v1/suppliers/{self.supplier_id}"
        # Without a reason nothing reaches the database.
        self.assertEqual(self.call("patch", path, {"image_url": None}).status_code, 422)
        self.engine.begin.assert_not_called()
        with patch("app.main.update_supplier", return_value=supplier_row()) as edit:
            response = self.call("patch", path, {"image_url": None}, **REASON)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(edit.call_args.kwargs["changes"], {"image_url": None})
        self.assertEqual(edit.call_args.kwargs["reason"], REASON["X-Admin-Reason"])

    def upload(self, data, filename="photo.jpg", content_type="image/jpeg", focus=None):
        return self.client.post("/api/v1/supplier-images", headers=self.token(),
                                files={"file": (filename, data, content_type)},
                                data={} if focus is None else {"focus": str(focus)})

    def stored(self, response):
        """The saved image behind an upload response."""
        served = self.client.get(response.json()["url"])
        return Image.open(io.BytesIO(served.content)).convert("RGB")

    @staticmethod
    def two_tone(size, split):
        """Red then blue, split across the height ("vertical") or the width."""
        image = Image.new("RGB", size, (255, 0, 0))
        width, height = size
        box = (0, height // 2, width, height) if split == "vertical" else (width // 2, 0, width, height)
        image.paste((0, 0, 255), box)
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    def test_uploads_are_cropped_to_the_card_at_the_chosen_position(self):
        tall = self.two_tone((900, 1600), "vertical")
        for focus, colour in ((0, (255, 0, 0)), (1, (0, 0, 255))):
            with self.subTest(focus=focus):
                image = self.stored(self.upload(tall, "tall.png", "image/png", focus=focus))
                self.assertEqual(image.size, (800, 450))
                # The middle of the kept strip is all one half of the photo.
                red, _, blue = image.getpixel((400, 225))
                self.assertEqual((red > 200, blue > 200), (colour[0] > 0, colour[2] > 0))
        wide = self.two_tone((3000, 1000), "horizontal")
        image = self.stored(self.upload(wide, "wide.png", "image/png", focus=1))
        self.assertEqual(image.size, (800, 450))
        self.assertGreater(image.getpixel((400, 225))[2], 200)

    def test_without_a_position_the_centre_is_kept(self):
        image = self.stored(self.upload(self.photo(size=(900, 1600))))
        self.assertEqual(image.size, (800, 450))

    def test_position_outside_zero_to_one_is_refused(self):
        for focus in (-0.1, 1.5, "top"):
            with self.subTest(focus=focus):
                self.assertEqual(self.upload(self.photo(), focus=focus).status_code, 422)
        self.assertEqual(os.listdir(self.image_dir.name), [])

    @staticmethod
    def photo(size=(2000, 1500), fmt="JPEG"):
        output = io.BytesIO()
        Image.new("RGB", size, (200, 120, 40)).save(output, format=fmt)
        return output.getvalue()

    def test_uploaded_image_is_shrunk_stored_and_public(self):
        response = self.upload(self.photo())
        self.assertEqual(response.status_code, 201)
        url = response.json()["url"]
        self.assertRegex(url, r"^/api/v1/supplier-images/[0-9a-f]{32}\.webp$")
        # Served without a token: an <img> tag cannot send one.
        served = self.client.get(url)
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served.headers["content-type"], "image/webp")
        with Image.open(io.BytesIO(served.content)) as stored:
            self.assertEqual(stored.format, "WEBP")
            self.assertLessEqual(max(stored.size), 800)
        self.engine.begin.assert_not_called()

    def test_png_is_accepted(self):
        self.assertEqual(self.upload(self.photo(fmt="PNG"), "logo.png", "image/png").status_code, 201)

    def test_non_images_and_oversized_files_are_refused(self):
        # The bytes decide, not the name or the claimed content type.
        self.assertEqual(self.upload(b"<script>alert(1)</script>", "x.jpg").status_code, 422)
        gif = io.BytesIO()
        Image.new("RGB", (10, 10)).save(gif, format="GIF")
        self.assertEqual(self.upload(gif.getvalue(), "x.gif", "image/gif").status_code, 422)
        self.assertEqual(self.upload(b"\xff" * (5 * 1024 * 1024 + 1)).status_code, 413)
        self.assertEqual(os.listdir(self.image_dir.name), [])

    def test_image_paths_cannot_escape_the_folder(self):
        self.assertEqual(self.client.get("/api/v1/supplier-images/../main.py").status_code, 404)

    def test_update_sends_only_the_supplied_fields(self):
        row = supplier_row(name="Renamed")
        with patch("app.main.update_supplier", return_value=row) as edit:
            self.call("patch", f"/api/v1/suppliers/{self.supplier_id}",
                      {"name": "Renamed"}, **REASON)
        self.assertEqual(edit.call_args.kwargs["changes"], {"name": "Renamed"})
