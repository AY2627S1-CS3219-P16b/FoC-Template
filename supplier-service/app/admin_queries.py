"""Admin write operations. Every change is recorded in the audit log.

Each function takes a transactional connection and writes the record and its
audit entry together, so a change can never exist without its audit entry.
Creates carry no reason: the new row is its own explanation.
"""

from datetime import date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError

from .places import normalize_place_name
from .schema import places, suppliers, supplier_audit_logs
from .supplier_queries import get_supplier


class DuplicateSupplierError(Exception):
    """A supplier with this name already exists in the same place and floor."""


class DuplicatePlaceError(Exception):
    """A place with an equivalent name already exists."""


class UnknownPlaceError(Exception):
    """The referenced place does not exist."""


class NoChangeError(Exception):
    """The request would leave the record exactly as it is."""


def _json_safe(value):
    """Values as JSON types, since times and UUIDs cannot be stored directly."""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def _record(connection, *, actor_id, entity_type, entity_id, action_type,
            previous_value, new_value, reason):
    connection.execute(supplier_audit_logs.insert().values(
        id=uuid4(),
        acting_admin_user_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action_type=action_type,
        previous_value=_json_safe(previous_value),
        new_value=_json_safe(new_value),
        reason=reason,
    ))


def _require_place(connection, place_id):
    if connection.scalar(select(places.c.id).where(places.c.id == place_id)) is None:
        raise UnknownPlaceError
    return place_id


def create_supplier(connection, *, actor_id: UUID, values: dict,
                    reason: str | None = None) -> dict:
    """Add a supplier, or raise if its place is unknown or the name is taken."""
    _require_place(connection, values["place_id"])
    supplier_id = uuid4()
    try:
        connection.execute(insert(suppliers).values(id=supplier_id, **values))
    except IntegrityError as error:
        # The name/place/floor unique constraint, which treats an unknown floor
        # as a value rather than as "any floor".
        raise DuplicateSupplierError from error
    _record(
        connection, actor_id=actor_id, entity_type="SUPPLIER", entity_id=supplier_id,
        action_type="SUPPLIER_CREATED", previous_value={},
        new_value={**values, "id": supplier_id}, reason=reason,
    )
    return get_supplier(connection, supplier_id)


def update_supplier(connection, *, actor_id: UUID, supplier_id: UUID,
                    changes: dict, reason: str) -> dict | None:
    """Apply the supplied fields to a supplier; None if it does not exist.

    Only fields the caller sent are touched, and only those that differ are
    written, so the audit entry shows the actual change rather than the whole
    record.
    """
    current = get_supplier(connection, supplier_id)
    if current is None:
        return None
    if "place_id" in changes:
        _require_place(connection, changes["place_id"])

    # get_supplier nests the place, so compare against the stored column.
    comparable = {**current, "place_id": current["place_id"]}
    differing = {
        field: value for field, value in changes.items()
        if comparable.get(field) != value
    }
    if not differing:
        raise NoChangeError
    previous = {field: comparable.get(field) for field in differing}

    try:
        connection.execute(
            update(suppliers).where(suppliers.c.id == supplier_id).values(**differing)
        )
    except IntegrityError as error:
        raise DuplicateSupplierError from error
    _record(
        connection, actor_id=actor_id, entity_type="SUPPLIER", entity_id=supplier_id,
        action_type="SUPPLIER_UPDATED", previous_value=previous,
        new_value=differing, reason=reason,
    )
    return get_supplier(connection, supplier_id)


def deactivate_supplier(connection, *, actor_id: UUID, supplier_id: UUID,
                        reason: str) -> dict | None:
    """Hide a supplier from browsing without deleting it; None if unknown.

    The row stays so orders that already reference it still resolve. Setting
    is_active back to true through the update endpoint restores it.
    """
    current = get_supplier(connection, supplier_id)
    if current is None:
        return None
    if not current["is_active"]:
        raise NoChangeError
    connection.execute(
        update(suppliers).where(suppliers.c.id == supplier_id).values(is_active=False)
    )
    _record(
        connection, actor_id=actor_id, entity_type="SUPPLIER", entity_id=supplier_id,
        action_type="SUPPLIER_DEACTIVATED", previous_value={"is_active": True},
        new_value={"is_active": False}, reason=reason,
    )
    return get_supplier(connection, supplier_id)


def count_audit_logs(connection) -> int:
    return connection.scalar(select(func.count()).select_from(supplier_audit_logs))


def list_audit_logs(connection, *, page: int, page_size: int) -> list[dict]:
    """One page of admin changes, newest first."""
    statement = (
        select(supplier_audit_logs)
        .order_by(supplier_audit_logs.c.created_at.desc(), supplier_audit_logs.c.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return [dict(row) for row in connection.execute(statement).mappings()]


def create_place(connection, *, actor_id: UUID, name: str,
                 parent_id: UUID | None, reason: str | None = None) -> dict:
    """Add a place, optionally inside an existing one.

    The search key is derived from the name and is unique, so a variant spelling
    of an existing place is rejected rather than creating a near-duplicate. A
    new place has no children yet, so nesting it cannot create a cycle.
    """
    if parent_id is not None:
        _require_place(connection, parent_id)
    search_key = normalize_place_name(name)
    if connection.scalar(
        select(places.c.id).where(places.c.search_key == search_key)
    ) is not None:
        raise DuplicatePlaceError
    place_id = uuid4()
    try:
        connection.execute(insert(places).values(
            id=place_id, name=name, parent_id=parent_id, search_key=search_key,
        ))
    except IntegrityError as error:
        raise DuplicatePlaceError from error
    _record(
        connection, actor_id=actor_id, entity_type="PLACE", entity_id=place_id,
        action_type="PLACE_CREATED", previous_value={},
        new_value={"id": place_id, "name": name, "parent_id": parent_id,
                   "search_key": search_key},
        reason=reason,
    )
    row = connection.execute(
        select(places.c.id, places.c.name, places.c.search_key, places.c.parent_id)
        .where(places.c.id == place_id)
    ).mappings().one()
    parent_name = None
    if parent_id is not None:
        parent_name = connection.scalar(
            select(places.c.name).where(places.c.id == parent_id)
        )
    return {**dict(row), "parent_name": parent_name}
