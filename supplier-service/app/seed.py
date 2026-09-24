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
from .places import canonical_place_records, normalize_place_name
from .classification import normalize_tags, validate_supplier_type
from .schema import places, metadata, suppliers


DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data/csv/supplier-seed-data.csv"
CSV_COLUMNS = {
    "Name", "Type", "Tags", "Building", "Floor", "Location Description", "Latitude",
    "Longitude", "StartingTime", "ClosingTime", "ImageURL",
}


def read_suppliers(path: Path) -> list[dict]:
    approved_keys = {record["search_key"] for record in canonical_place_records()}
    content = path.read_text(encoding="utf-8-sig")
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

            place_key = normalize_place_name(values["Building"])
            if place_key not in approved_keys:
                raise ValueError(
                    f"Unknown place {values['Building']!r}; add its canonical name "
                    "to CANONICAL_PLACES in app/places.py first"
                )

            def parse_time(value):
                return datetime.strptime(value, "%H%Mhrs").time() if value else None

            supplier_type = validate_supplier_type(values["Type"])
            tags = normalize_tags(values["Tags"].split(";") if values["Tags"] else [])
            # Stable IDs let repeat imports skip existing records without
            # overwriting later admin edits or reactivating removed suppliers.
            identity = json.dumps([values["Name"], place_key, values["Floor"]])
            record = {
                "id": uuid5(NAMESPACE_URL, "foc:template-supplier:" + identity),
                "name": values["Name"],
                "supplier_type": supplier_type,
                "tags": tags,
                "place_key": place_key,
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


def seed_records(connection, records: list[dict]) -> tuple[int, int]:
    """Import in the caller's transaction; existing rows remain unchanged."""
    canonical = canonical_place_records()
    approved_keys = {record["search_key"] for record in canonical}
    unknown = {record["place_key"] for record in records} - approved_keys
    if unknown:
        raise ValueError(f"Unknown place keys: {sorted(unknown)}")
    # Resolve parents using actual database IDs, including pre-existing admin rows.
    place_ids = dict(connection.execute(select(places.c.search_key, places.c.id)).all())
    for record in canonical:
        values = {key: value for key, value in record.items() if key != "parent_key"}
        values["parent_id"] = place_ids[record["parent_key"]] if record["parent_key"] else None
        connection.execute(insert(places).values(**values).on_conflict_do_nothing(
            index_elements=[places.c.search_key]
        ))
        place_ids[record["search_key"]] = connection.scalar(
            select(places.c.id).where(places.c.search_key == record["search_key"])
        )
    resolved = [
        {**{key: value for key, value in record.items() if key != "place_key"},
         "place_id": place_ids[record["place_key"]]}
        for record in records
    ]
    inserted = 0
    if resolved:
        statement = insert(suppliers).values(resolved).on_conflict_do_nothing(
            index_elements=[suppliers.c.id]
        ).returning(suppliers.c.id)
        inserted = len(connection.execute(statement).all())
    total = connection.execute(select(func.count()).select_from(suppliers)).scalar_one()
    return inserted, total


def seed(engine, records: list[dict]) -> tuple[int, int]:
    with engine.begin() as connection:
        metadata.create_all(connection)
        inserted, total = seed_records(connection, records)
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
