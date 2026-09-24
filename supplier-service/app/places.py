"""Canonical display names and shared place-name matching rules."""

import unicodedata
from uuid import NAMESPACE_URL, uuid5


# Author display names here; CSV ordering must not determine their spelling.
# These are named campus places from the supplied dataset, including areas.
CANONICAL_PLACES = (
    ('Blk AS8', None),
    ('COM2', None),
    ('COM3', None),
    ('Central Library', None),
    ('Engineering Block E3', None),
    ('Engineering Block E4', None),
    ('Engineering Block EA', None),
    ('LT27', None),
    ('Hon Sui Sen Memorial Library', None),
    ('Medicine+Science Library', None),
    ("Prince George's Park", None),
    ('The Ridge', None),
    ('Yusof Ishak House', None),
    ('innovation4.0', None),
    ('Frontier', 'LT27'),
    ('The Terrace', 'COM3'),
)


def normalize_place_name(value: str) -> str:
    """Match case, spacing and punctuation variants, not semantic aliases."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    key = "".join(character for character in normalized if character.isalnum())
    if not key:
        raise ValueError("place name must contain letters or numbers")
    return key


def canonical_place_records() -> list[dict]:
    records = []
    keys = set()
    for name, parent in CANONICAL_PLACES:
        key = normalize_place_name(name)
        if key in keys:
            raise ValueError(f"Duplicate canonical place key: {key}")
        keys.add(key)
        records.append({
            "id": uuid5(NAMESPACE_URL, "foc:place:" + key),
            "name": name,
            "search_key": key,
            "parent_key": normalize_place_name(parent) if parent else None,
        })
    parents = {row["search_key"]: row["parent_key"] for row in records}
    for key in parents:
        visited = set()
        current = key
        while current is not None:
            if current in visited:
                raise ValueError("Canonical places contain a cycle")
            if current not in parents:
                raise ValueError(f"Unknown parent place: {current}")
            visited.add(current)
            current = parents[current]
    # Parent-first order, independent of authored list ordering.
    def depth(row):
        level, parent = 0, row["parent_key"]
        while parent is not None:
            level += 1
            parent = parents[parent]
        return level
    return sorted(records, key=depth)


def place_key_default(context) -> str:
    """Generate the key for SQLAlchemy inserts that supply a name.

    Future rename operations must update name and normalized key together.
    """
    return normalize_place_name(context.get_current_parameters()["name"])
