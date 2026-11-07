import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from uuid import uuid4

from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import IntegrityError, StatementError

from app.classification import (
    MAX_TAG_LENGTH, MAX_TAGS, normalize_tag,
    normalize_tags, validate_supplier_type,
)
from app.database import create_database_engine
from app.schema import places, suppliers
from app.seed import DEFAULT_CSV, read_suppliers, seed


class ClassificationTests(unittest.TestCase):
    def test_open_vocabulary_normalized_and_deduplicated(self):
        self.assertEqual(normalize_tags(["Coffee", " coffee ", "BUBBLE   TEA"]),
                         ["bubble tea", "coffee"])
        self.assertEqual(normalize_tags(["New Specialty"]), ["new specialty"])
        self.assertEqual(normalize_tags([]), [])
        self.assertEqual(normalize_tag("Ｃｏｆｆｅｅ"), "coffee")

    def test_invalid_tags_are_rejected(self):
        for values in (None, "coffee", [None], [""], ["  "], ["---"], [["coffee"]],
                       ["a\x00b"], ["x" * (MAX_TAG_LENGTH + 1)],
                       [f"tag {i}" for i in range(MAX_TAGS + 1)]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                normalize_tags(values)

    def test_csv_categories_and_tags(self):
        with self.assertRaises(ValueError):
            validate_supplier_type("COFFEE")
        rows = read_suppliers(DEFAULT_CSV)
        # Every category is used, and nothing outside them; counts grow with the CSV.
        self.assertEqual(set(Counter(row["supplier_type"] for row in rows)),
                         {"FOOD_BEVERAGE", "RETAIL", "FACILITY"})
        self.assertGreater(sum("coffee" in row["tags"] for row in rows), 0)

    def test_unknown_csv_type_is_not_silently_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text(DEFAULT_CSV.read_text(encoding="utf-8-sig").replace(
                ",FOOD_BEVERAGE,", ",Mystery,", 1
            ))
            with self.assertRaisesRegex(ValueError, "CSV row 2: supplier_type must be one of"):
                read_suppliers(path)

    def test_csv_tags_are_read_directly_and_invalid_values_rejected(self):
        import csv
        import io
        original = list(csv.DictReader(io.StringIO(DEFAULT_CSV.read_text(encoding="utf-8-sig"))))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tags.csv"
            for tags, expected in (("Breakfast; breakfast ", ["breakfast"]), ("", []),
                                   ("   ", []), ("coffee", ["coffee"]),
                                   ("coffee;halal", ["coffee", "halal"]),
                                   ("coffee;", None), ("---", None)):
                rows = [dict(row) for row in original]
                rows[0]["Tags"] = tags
                with path.open("w", newline="") as output:
                    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                if expected is not None:
                    self.assertEqual(read_suppliers(path)[0]["tags"], expected)
                else:
                    with self.assertRaisesRegex(ValueError, "CSV row 2:"):
                        read_suppliers(path)


@unittest.skipUnless(os.getenv("RUN_POSTGRES_TESTS") == "1", "Set RUN_POSTGRES_TESTS=1 for PostgreSQL checks")
class ClassificationDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_database_engine()
        cls.schema = "supplier_types_test_" + uuid4().hex
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

    def test_category_tag_storage_and_constraints(self):
        records = read_suppliers(DEFAULT_CSV)
        self.assertEqual(seed(self.db, records), (len(records), len(records)))
        with self.db.begin() as connection:
            stored = connection.execute(select(suppliers)).mappings().all()
            # Stored exactly as read from the CSV.
            self.assertEqual(Counter(row["supplier_type"] for row in stored),
                             Counter(record["supplier_type"] for record in records))
            self.assertEqual(sum("coffee" in row["tags"] for row in stored),
                             sum("coffee" in record["tags"] for record in records))
            from app.supplier_queries import list_suppliers
            # A search finds suppliers tagged "coffee" as well as those with it
            # in their name (e.g. Luckin Coffee); no place name contains it.
            expected = {r["id"] for r in records
                        if "coffee" in r["tags"] or "coffee" in r["name"].casefold()}
            self.assertTrue(any("coffee" in r["tags"] and "coffee" not in r["name"].casefold()
                                for r in records))   # some match only through a tag
            for search in ("cof", "coffee", "COFFEE"):
                matches = list_suppliers(connection, search=search)
                self.assertEqual({row["id"] for row in matches}, expected)

            place_id = connection.scalar(select(places.c.id).limit(1))
            row = connection.execute(insert(suppliers).values(
                name="New cafe", supplier_type="FOOD_BEVERAGE", place_id=place_id,
                tags=[" Coffee ", "coffee", "BUBBLE   TEA"],
                opening_time="08:00", closing_time="18:00", operating_days=["MON"],
            ).returning(suppliers)).mappings().one()
            self.assertEqual(row["tags"], ["bubble tea", "coffee"])
            connection.execute(update(suppliers).where(suppliers.c.id == row["id"]).values(
                tags=["New Tag", " NEW TAG "], is_active=False
            ))
            self.assertEqual(connection.scalar(select(suppliers.c.tags).where(suppliers.c.id == row["id"])),
                             ["new tag"])
            for changes in ({"supplier_type": "COFFEE"}, {"tags": [""]}, {"tags": None}):
                with self.assertRaises((IntegrityError, StatementError)):
                    with connection.begin_nested():
                        connection.execute(update(suppliers).where(suppliers.c.id == row["id"]).values(**changes))
            # Existing seed records may be reclassified by admins; reseeding preserves edits.
            connection.execute(update(suppliers).where(suppliers.c.id == records[0]["id"]).values(
                tags=["Admin Tag"], supplier_type="RETAIL"
            ))
        # The CSV rows plus the "New cafe" added above.
        self.assertEqual(seed(self.db, records), (0, len(records) + 1))
        with self.db.connect() as connection:
            row = connection.execute(select(suppliers).where(suppliers.c.id == records[0]["id"])).mappings().one()
            self.assertEqual(row["tags"], ["admin tag"])
            self.assertEqual(row["supplier_type"], "RETAIL")


if __name__ == "__main__":
    unittest.main()
