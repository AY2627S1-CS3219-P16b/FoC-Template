import csv
import io
import os
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from app.places import canonical_place_records, normalize_place_name
from app.database import create_database_engine
from app.schema import places, suppliers
from app.seed import DEFAULT_CSV, read_suppliers, seed


# Required columns, supplied where the test is about some other constraint.
HOURS = {"opening_time": "08:00", "closing_time": "18:00"}


class PlaceNormalizationTests(unittest.TestCase):
    def test_formatting_variants_match(self):
        for value in ("COM 2", "com2", "Com  2", "C O M 2", "Com-2"):
            self.assertEqual(normalize_place_name(value), "com2")
        self.assertEqual(normalize_place_name("Prince George’s Park"),
                         normalize_place_name("Prince George's Park"))
        self.assertNotEqual(normalize_place_name("Computing 2"), "com2")

    def test_empty_key_is_rejected(self):
        for value in ("", "  ", "---"):
            with self.assertRaises(ValueError):
                normalize_place_name(value)

    def test_csv_matches_authored_names(self):
        rows = read_suppliers(DEFAULT_CSV)
        self.assertEqual(len(rows), 21)
        instachef = next(row for row in rows if row["name"] == "InstaChef")
        self.assertEqual(instachef["place_key"], "com3")
        self.assertEqual(instachef["location_description"], "Beside Terrace, near the foyer")
        smooy = next(row for row in rows if row["name"] == "Smooy")
        self.assertEqual(smooy["place_key"], "com3")
        self.assertEqual(smooy["location_description"], "Beside Terrace")
        self.assertEqual(sum(row["place_key"] == "com2" for row in rows), 2)
        self.assertEqual(sum(row["place_key"] == "princegeorgespark" for row in rows), 3)
        names = {row["search_key"]: row["name"] for row in canonical_place_records()}
        self.assertEqual(names["com2"], "COM2")
        self.assertEqual(names["princegeorgespark"], "Prince George's Park")

    def test_unknown_place_fails_with_row_number(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "suppliers.csv"
            path.write_text(DEFAULT_CSV.read_text(encoding="utf-8-sig").replace(
                "Central Library", "Unknown Campus Place", 1
            ))
            with self.assertRaisesRegex(ValueError, "CSV row 2: Unknown place"):
                read_suppliers(path)

    def test_seed_identity_survives_place_formatting_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "suppliers.csv"
            reader = csv.DictReader(io.StringIO(DEFAULT_CSV.read_text(encoding="utf-8-sig")))
            with path.open("w", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
                writer.writeheader()
                for row in reader:
                    if row["Building"] == "COM2":
                        row["Building"] = "Com 2"
                    writer.writerow(row)
            self.assertEqual(read_suppliers(path), read_suppliers(DEFAULT_CSV))


@unittest.skipUnless(os.getenv("RUN_POSTGRES_TESTS") == "1", "Set RUN_POSTGRES_TESTS=1 for PostgreSQL checks")
class PlaceDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_database_engine()
        cls.schema = "supplier_test_" + uuid4().hex
        with cls.engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{cls.schema}"'))
        cls.db = cls.engine.execution_options(schema_translate_map={None: cls.schema})

    @classmethod
    def tearDownClass(cls):
        try:
            with cls.engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{cls.schema}" CASCADE'))
        finally:
            cls.engine.dispose()

    def test_import_matching_constraints_and_preservation(self):
        records = read_suppliers(DEFAULT_CSV)
        self.assertEqual(seed(self.db, records), (21, 21))
        self.assertEqual(seed(self.db, records), (0, 21))
        with self.db.begin() as connection:
            self.assertEqual(connection.scalar(select(func.count()).select_from(places)), 16)
            for value, expected in (("COM 2", 2), ("com2", 2), ("Com2", 2), ("Frontier", 1), ("The Terrace", 0),
                                    ("Prince George’s Park", 3), ("Prince George's Park", 3)):
                count = connection.scalar(select(func.count()).select_from(
                    suppliers.join(places)
                ).where(places.c.search_key == normalize_place_name(value)))
                self.assertEqual(count, expected)
            ids = dict(connection.execute(select(places.c.search_key, places.c.id)).all())
            self.assertEqual(connection.scalar(select(places.c.parent_id).where(
                places.c.id == ids["frontier"])), ids["lt27"])
            self.assertEqual(connection.scalar(select(places.c.parent_id).where(
                places.c.id == ids["theterrace"])), ids["com3"])
            # Database constraints protect parent references independently of APIs.
            for statement in (
                delete(places).where(places.c.id == ids["lt27"]),
                update(places).where(places.c.id == ids["com3"]).values(parent_id=ids["com3"]),
                update(places).where(places.c.id == ids["com3"]).values(parent_id=uuid4()),
            ):
                with self.assertRaises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(statement)
            place_id = connection.scalar(select(places.c.id).where(places.c.search_key == "com2"))
            invalid_operations = [
                delete(places).where(places.c.id == place_id),
                insert(places).values(name="COM 2"),
                insert(suppliers).values(name="Bad FK", supplier_type="FOOD_BEVERAGE", place_id=uuid4(), **HOURS),
                insert(suppliers).values(name="No place", supplier_type="FOOD_BEVERAGE", **HOURS),
                insert(suppliers).values(name=" ", supplier_type="FOOD_BEVERAGE", place_id=place_id, **HOURS),
                insert(suppliers).values(name="Bad coordinate", supplier_type="FOOD_BEVERAGE", place_id=place_id, latitude=91, **HOURS),
                # Hours are required, so Order Service can tell whether a supplier is open.
                insert(suppliers).values(name="No hours", supplier_type="FOOD_BEVERAGE", place_id=place_id),
            ]
            for statement in invalid_operations:
                with self.assertRaises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(statement)
            # Unknown floors must not bypass supplier uniqueness, and neither
            # must a different spelling of the same name.
            values = dict(name="Duplicate test", supplier_type="FOOD_BEVERAGE",
                          place_id=place_id, **HOURS)
            connection.execute(insert(suppliers).values(**values))
            for spelling in ("Duplicate test", "duplicate  test", "DUPLICATE-TEST"):
                with self.assertRaises(IntegrityError, msg=spelling):
                    with connection.begin_nested():
                        connection.execute(
                            insert(suppliers).values({**values, "name": spelling})
                        )
            # A different name at the same place is a separate supplier, not a
            # duplicate: the rule compares spellings, not meanings.
            connection.execute(insert(suppliers).values(
                {**values, "name": "Duplicate test @ NUS"}
            ))
            # A different floor is a separate branch of the same shop.
            connection.execute(insert(suppliers).values({**values, "floor": "2"}))
            connection.execute(delete(suppliers).where(
                suppliers.c.name.like("Duplicate test%")
            ))
            connection.execute(update(suppliers).where(suppliers.c.id == records[0]["id"]).values(
                name="Edited supplier", is_active=False
            ))
        self.assertEqual(seed(self.db, records), (0, 21))
        with self.db.connect() as connection:
            row = connection.execute(select(suppliers).where(suppliers.c.id == records[0]["id"])).mappings().one()
            self.assertEqual(row["name"], "Edited supplier")
            self.assertFalse(row["is_active"])


if __name__ == "__main__":
    unittest.main()
