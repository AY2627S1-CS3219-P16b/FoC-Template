import os
import unittest
from datetime import datetime, time, timezone
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.database import create_database_engine
from app.hours import CAMPUS_TIMEZONE, DAYS, is_open, normalize_days, parse_days
from app.schema import create_schema, metadata, suppliers

WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI"]


def at(day: str, hour: int, minute: int = 0) -> datetime:
    """A campus time in the week of Monday 2026-10-12."""
    return datetime(2026, 10, 12 + DAYS.index(day), hour, minute, tzinfo=CAMPUS_TIMEZONE)


class OperatingDayTests(unittest.TestCase):
    def test_days_are_normalized_into_week_order(self):
        self.assertEqual(normalize_days(["fri", " MON ", "wed", "MON"]), ["MON", "WED", "FRI"])

    def test_invalid_days_are_rejected(self):
        for values in ([], ["FUNDAY"], ["Monday"], [""]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                normalize_days(values)

    def test_csv_shorthand(self):
        self.assertEqual(parse_days("DAILY"), list(DAYS))
        self.assertEqual(parse_days("MON-FRI"), WEEKDAYS)
        self.assertEqual(parse_days("mon-sat"), WEEKDAYS + ["SAT"])
        self.assertEqual(parse_days("MON,WED,FRI"), ["MON", "WED", "FRI"])
        self.assertEqual(parse_days("MON-TUE,SUN"), ["MON", "TUE", "SUN"])
        for value in ("", "FRI-MON", "MON-FUN", "SOMETIMES"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_days(value)


class IsOpenTests(unittest.TestCase):
    def test_daytime_hours_on_operating_days_only(self):
        hours = (time(8, 0), time(18, 0), WEEKDAYS)
        self.assertTrue(is_open(*hours, at("MON", 8)))
        self.assertTrue(is_open(*hours, at("FRI", 17, 59)))
        self.assertFalse(is_open(*hours, at("MON", 7, 59)))
        self.assertFalse(is_open(*hours, at("MON", 18)))
        self.assertFalse(is_open(*hours, at("SAT", 12)))
        self.assertFalse(is_open(*hours, at("SUN", 12)))

    def test_open_all_day_follows_operating_days(self):
        self.assertTrue(is_open(time(0, 0), time(23, 59), list(DAYS), at("SUN", 23, 59)))
        self.assertTrue(is_open(time(0, 0), time(23, 59), list(DAYS), at("MON", 0)))
        self.assertFalse(is_open(time(0, 0), time(23, 59), WEEKDAYS, at("SAT", 3)))

    def test_past_midnight_belongs_to_the_day_the_shift_started(self):
        # Supersnacks-style 18:00 to 02:00, trading Monday to Friday nights.
        hours = (time(18, 0), time(2, 0), WEEKDAYS)
        self.assertTrue(is_open(*hours, at("FRI", 23)))
        self.assertTrue(is_open(*hours, at("SAT", 1, 30)))   # Friday night's shift
        self.assertFalse(is_open(*hours, at("SAT", 2)))
        self.assertFalse(is_open(*hours, at("SAT", 19)))     # no Saturday shift
        self.assertFalse(is_open(*hours, at("MON", 1)))      # Sunday had no shift
        self.assertFalse(is_open(*hours, at("MON", 12)))

    def test_times_are_read_in_campus_time(self):
        # 01:00 UTC on Monday is 09:00 on campus.
        utc = datetime(2026, 10, 12, 1, 0, tzinfo=timezone.utc)
        self.assertTrue(is_open(time(8, 0), time(18, 0), WEEKDAYS, utc))


@unittest.skipUnless(os.getenv("RUN_POSTGRES_TESTS") == "1", "Set RUN_POSTGRES_TESTS=1 for PostgreSQL checks")
class OperatingDaysUpgradeTests(unittest.TestCase):
    """A database created before operating days existed gains the column."""

    def setUp(self):
        self.engine = create_database_engine()
        self.schema = "supplier_upgrade_test_" + uuid4().hex
        with self.engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.db = self.engine.execution_options(schema_translate_map={None: self.schema})

    def tearDown(self):
        try:
            with self.engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        finally:
            self.engine.dispose()

    def test_existing_suppliers_become_open_every_day_and_new_rows_need_days(self):
        with self.db.begin() as connection:
            metadata.create_all(connection)
            # Recreate the shape from before this change.
            connection.execute(text(
                f'ALTER TABLE "{self.schema}".suppliers DROP COLUMN operating_days'))
            place_id = connection.execute(text(
                f"INSERT INTO \"{self.schema}\".places (id, name, search_key) "
                f"VALUES (gen_random_uuid(), 'COM2', 'com2') RETURNING id")).scalar_one()
            connection.execute(text(
                f"INSERT INTO \"{self.schema}\".suppliers "
                f"(id, name, supplier_type, tags, place_id, opening_time, closing_time) "
                f"VALUES (gen_random_uuid(), 'Old', 'FOOD_BEVERAGE', '{{}}', :place, "
                f"'08:00', '18:00')"), {"place": place_id})

        for _ in range(2):  # Running it again must be harmless.
            with self.db.begin() as connection:
                create_schema(connection)

        with self.db.begin() as connection:
            self.assertEqual(connection.scalar(select(suppliers.c.operating_days)), list(DAYS))
            # No default is left behind: a new row must still state its days.
            for days in (None, [], ["FUN"]):
                values = dict(id=uuid4(), name=f"New {days}", supplier_type="FOOD_BEVERAGE",
                              tags=[], place_id=place_id, opening_time="08:00",
                              closing_time="18:00")
                if days is not None:
                    values["operating_days"] = days
                with self.subTest(days=days), self.assertRaises(IntegrityError):
                    with connection.begin_nested():
                        connection.execute(suppliers.insert().values(**values))


if __name__ == "__main__":
    unittest.main()
