"""Shared category and tag rules for seeding and future admin API writes."""

import unicodedata

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import TypeDecorator


SUPPLIER_TYPES = ("FOOD_BEVERAGE", "RETAIL", "FACILITY")
MAX_TAGS = 10
MAX_TAG_LENGTH = 40

def validate_supplier_type(value: str) -> str:
    if value not in SUPPLIER_TYPES:
        raise ValueError(f"supplier_type must be one of {', '.join(SUPPLIER_TYPES)}")
    return value


def normalize_tag(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("each tag must be text")
    tag = " ".join(unicodedata.normalize("NFKC", value).casefold().split())
    if not tag or not any(character.isalnum() for character in tag):
        raise ValueError("tags must contain letters or numbers")
    if not tag.isprintable():
        raise ValueError("tags must not contain control characters")
    if len(tag) > MAX_TAG_LENGTH:
        raise ValueError(f"tags must not exceed {MAX_TAG_LENGTH} characters")
    return tag


def normalize_tags(values: list[str]) -> list[str]:
    if not isinstance(values, list):
        raise ValueError("tags must be a list of strings")
    tags = sorted({normalize_tag(value) for value in values})
    if len(tags) > MAX_TAGS:
        raise ValueError(f"a supplier can have at most {MAX_TAGS} distinct tags")
    return tags


class SupplierTags(TypeDecorator):
    """PostgreSQL TEXT[] normalizing writes and array-valued comparison binds.

    contains([...]) and overlap([...]) normalize array arguments. Scalar
    any(value) does not pass through normalize_tags. Future tag filtering must
    normalize request input and use array-valued containment/overlap operators.

    Future admin request models must call normalize_tags before database writes
    to return HTTP 422 for invalid input. Request models are deferred to the
    endpoint work. Bind-time validation is a fallback for internal writes, not
    HTTP validation (SQLAlchemy wraps its errors in StatementError).
    Raw SQL bypasses this Python rule.
    """

    impl = ARRAY(Text)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return normalize_tags(value)
