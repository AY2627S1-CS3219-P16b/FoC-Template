"""Run with `python -m app.seed` from supplier-service/."""

import argparse
import csv
import io
import json
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from .database import create_database_engine
from .schema import metadata, suppliers


DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data/csv/supplier-seed-data.csv"
CSV_COLUMNS = {
    "Name", "Type", "Building", "Floor", "Location Description", "Latitude",
    "Longitude", "StartingTime", "ClosingTime", "ImageURL",
}


def read_suppliers(path: Path) -> list[dict]:
    raw = path.read_bytes()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # The supplied CSV uses Windows smart apostrophes in some locations.
        content = raw.decode("cp1252")
    reader = csv.DictReader(io.StringIO(content))
    if not CSV_COLUMNS.issubset(reader.fieldnames or []):
        raise ValueError("CSV is missing required supplier columns")

    records = []
    for line_number, row in enumerate(reader, start=2):
        try:
            values = {key: (row.get(key) or "").strip() for key in CSV_COLUMNS}
            for required in ("Name", "Type", "Building"):
                if not values[required]:
                    raise ValueError(f"{required} must not be empty")

            def parse_time(value):
                return datetime.strptime(value, "%H%Mhrs").time() if value else None

            # Stable IDs let repeat imports skip existing records without
            # overwriting later admin edits or reactivating removed suppliers.
            identity = json.dumps([values[k] for k in ("Name", "Building", "Floor")])
            record = {
                "id": uuid5(NAMESPACE_URL, "foc:template-supplier:" + identity),
                "name": values["Name"],
                "supplier_type": values["Type"],
                "building": values["Building"],
                "floor": values["Floor"] or None,
                "location_description": values["Location Description"] or None,
                "latitude": float(values["Latitude"]) if values["Latitude"] else None,
                "longitude": float(values["Longitude"]) if values["Longitude"] else None,
                "opening_time": parse_time(values["StartingTime"]),
                "closing_time": parse_time(values["ClosingTime"]),
                "image_url": values["ImageURL"] or None,
            }
            for field, limit in (("latitude", 90), ("longitude", 180)):
                if record[field] is not None and not -limit <= record[field] <= limit:
                    raise ValueError(f"{field} out of range")
            records.append(record)
        except (ValueError, TypeError) as error:
            raise ValueError(f"CSV row {line_number}: {error}") from error
    return records


def seed(engine, records: list[dict]) -> tuple[int, int]:
    metadata.create_all(engine)
    with engine.begin() as connection:
        inserted = 0
        if records:
            statement = insert(suppliers).values(records).on_conflict_do_nothing(
                index_elements=[suppliers.c.id]
            ).returning(suppliers.c.id)
            inserted = len(connection.execute(statement).all())
        total = connection.execute(select(func.count()).select_from(suppliers)).scalar_one()
    return inserted, total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()
    records = read_suppliers(args.csv)
    engine = create_database_engine()
    try:
        inserted, total = seed(engine, records)
        print(f"Loaded {len(records)} CSV rows; inserted {inserted}; suppliers in database: {total}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
