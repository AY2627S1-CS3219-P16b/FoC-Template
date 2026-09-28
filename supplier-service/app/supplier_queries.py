"""Read queries backing the supplier browse, search, and filter endpoints."""

from uuid import UUID

from sqlalchemy import func, or_, select

from .classification import validate_supplier_type
from .places import normalize_place_name
from .schema import places, suppliers


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

DEFAULT_SORT = "name"

# Self-join so a supplier can report the place it sits in and that place's parent.
parent_places = places.alias("parent_places")

_SUPPLIER_SOURCE = (
    suppliers
    .join(places, suppliers.c.place_id == places.c.id)
    .outerjoin(parent_places, places.c.parent_id == parent_places.c.id)
)

_SUPPLIER_COLUMNS = (
    suppliers.c.id,
    suppliers.c.name,
    suppliers.c.supplier_type,
    suppliers.c.tags,
    suppliers.c.floor,
    suppliers.c.location_description,
    suppliers.c.latitude,
    suppliers.c.longitude,
    suppliers.c.opening_time,
    suppliers.c.closing_time,
    suppliers.c.image_url,
    suppliers.c.pickup_instructions,
    suppliers.c.is_active,
    places.c.id.label("place_id"),
    places.c.name.label("place_name"),
    parent_places.c.id.label("place_parent_id"),
    parent_places.c.name.label("place_parent_name"),
)


# A "-" prefix reverses the key, matching the usual REST convention.
SORT_OPTIONS = {
    "name": (suppliers.c.name.asc(),),
    "-name": (suppliers.c.name.desc(),),
    # Grouping by place is only useful if suppliers stay ordered within it.
    "place": (places.c.name.asc(), suppliers.c.name.asc()),
    "-place": (places.c.name.desc(), suppliers.c.name.asc()),
    "category": (suppliers.c.supplier_type.asc(), suppliers.c.name.asc()),
    "-category": (suppliers.c.supplier_type.desc(), suppliers.c.name.asc()),
}


def place_and_descendant_ids(place_id):
    """The given place plus every place nested below it, at any depth.

    UNION rather than UNION ALL so an unexpected cycle still terminates.
    """
    tree = (
        select(places.c.id)
        .where(places.c.id == place_id)
        .cte("place_tree", recursive=True)
    )
    return tree.union(select(places.c.id).join(tree, places.c.parent_id == tree.c.id))


def places_matching_text_ids(search: str):
    """Places whose name matches the text, plus everything nested below them.

    Typing a building must behave like filtering by it: someone searching
    "LT27" expects Frontier's suppliers without knowing Frontier sits inside
    LT27. Seeding the same recursive walk from a name match keeps search and
    the location filter consistent.
    """
    pattern = f"%{search}%"
    seeds = [places.c.name.ilike(pattern)]
    try:
        # Lets "com 2" match COM2, the way the location filter already does.
        seeds.append(places.c.search_key.contains(normalize_place_name(search)))
    except ValueError:
        pass  # Text with no letters or digits cannot match a search key.
    tree = select(places.c.id).where(or_(*seeds)).cte("matched_places", recursive=True)
    return tree.union(select(places.c.id).join(tree, places.c.parent_id == tree.c.id))


def resolve_place_id(connection, value: str):
    """Accept a place UUID or its search key; return the place id, or None.

    Search keys read better in a URL (`?place=com2`) and are unique, so both
    forms work.
    """
    try:
        candidate = UUID(value)
    except (AttributeError, TypeError, ValueError):
        candidate = None
    if candidate is not None:
        return connection.scalar(select(places.c.id).where(places.c.id == candidate))
    return connection.scalar(
        select(places.c.id).where(places.c.search_key == normalize_place_name(value))
    )


def _conditions(*, search=None, supplier_type=None, place_id=None,
                include_inactive=False):
    conditions = []
    if not include_inactive:
        conditions.append(suppliers.c.is_active.is_(True))
    if supplier_type is not None:
        conditions.append(
            suppliers.c.supplier_type == validate_supplier_type(supplier_type)
        )
    if place_id is not None:
        # Suppliers sit in the most specific place, so a filter on a building
        # must also return suppliers in the venues inside it.
        conditions.append(
            suppliers.c.place_id.in_(select(place_and_descendant_ids(place_id).c.id))
        )
    if search and search.strip():
        # One box covers the three things people actually type: a supplier
        # name, a place (at or below a matching one), or an offering such as
        # "coffee" that only appears as a tag. Directions in
        # location_description stay excluded to avoid loose matches.
        text = search.strip()
        pattern = f"%{text}%"
        conditions.append(
            or_(
                suppliers.c.name.ilike(pattern),
                suppliers.c.place_id.in_(select(places_matching_text_ids(text).c.id)),
                # Search partial tag text through the same input as names.
                func.array_to_string(suppliers.c.tags, " ").ilike(pattern),
            )
        )
    return conditions


def count_suppliers(connection, **filters) -> int:
    statement = select(func.count()).select_from(_SUPPLIER_SOURCE)
    for condition in _conditions(**filters):
        statement = statement.where(condition)
    return connection.scalar(statement)


def sort_clauses(sort: str):
    """Ordering for a sort key, or raise ValueError for an unknown one.

    Every option ends with the supplier id so ties are broken consistently;
    without it a shared sort value could let a row repeat or vanish between
    pages.
    """
    try:
        columns = SORT_OPTIONS[sort or DEFAULT_SORT]
    except KeyError as error:
        raise ValueError(
            f"sort must be one of {', '.join(SORT_OPTIONS)}"
        ) from error
    return (*columns, suppliers.c.id)


def list_suppliers(connection, *, page=1, page_size=DEFAULT_PAGE_SIZE,
                   sort=None, **filters):
    """One page of suppliers, ordered so paging is stable."""
    statement = select(*_SUPPLIER_COLUMNS).select_from(_SUPPLIER_SOURCE)
    for condition in _conditions(**filters):
        statement = statement.where(condition)
    statement = (
        statement
        .order_by(*sort_clauses(sort))
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return [dict(row) for row in connection.execute(statement).mappings()]


def get_supplier(connection, supplier_id):
    """One supplier regardless of active status, or None.

    Order Service resolves suppliers referenced by existing orders, so a
    deactivated supplier is returned with its flag rather than hidden.
    """
    statement = (
        select(*_SUPPLIER_COLUMNS)
        .select_from(_SUPPLIER_SOURCE)
        .where(suppliers.c.id == supplier_id)
    )
    row = connection.execute(statement).mappings().one_or_none()
    return dict(row) if row is not None else None


def list_places(connection):
    """Every place with its parent, for filter dropdowns and admin pickers."""
    statement = (
        select(
            places.c.id,
            places.c.name,
            places.c.search_key,
            places.c.parent_id,
            parent_places.c.name.label("parent_name"),
        )
        .select_from(
            places.outerjoin(parent_places, places.c.parent_id == parent_places.c.id)
        )
        .order_by(places.c.name)
    )
    return [dict(row) for row in connection.execute(statement).mappings()]
