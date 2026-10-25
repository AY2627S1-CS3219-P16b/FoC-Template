"""Optional real pgvector checks; use a disposable database ending in _test."""

import os
from uuid import uuid4

import pytest
from sqlalchemy.engine import make_url

from app.database import IndexNotReady, Store, create_database
from app.knowledge import Chunk, Corpus


def test_real_pgvector_index_refresh_and_stale_version():
    url = os.getenv("FAQ_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set FAQ_TEST_DATABASE_URL to a disposable PostgreSQL/pgvector database.")
    assert make_url(url).database.endswith("_test"), "Only disposable *_test databases are allowed."
    engine = create_database(url)
    try:
        store = Store(engine)
        store.initialize()
        first = Corpus([Chunk("a", "credits.md", "Credits", "Starting credits?", "20 credits.")], "a" * 64)
        store.replace_index(first, [[1.0] + [0.0] * 383])
        assert store.status(first.version)
        matches = store.retrieve([1.0] + [0.0] * 383, first.version, 0.65)
        assert matches[0]["id"] == "a" and matches[0]["score"] == pytest.approx(1.0)
        assert store.retrieve([0.0, 1.0] + [0.0] * 382, first.version, 0.65) == []
        second = Corpus([Chunk("b", "account.md", "Account", "Delete account?", "Not available.")], "b" * 64)
        store.replace_index(second, [[0.0, 1.0] + [0.0] * 382])
        assert not store.status(first.version)
        with pytest.raises(IndexNotReady):
            store.retrieve([1.0] + [0.0] * 383, first.version, 0)
        assert [row["id"] for row in store.retrieve([0.0, 1.0] + [0.0] * 382, second.version, 0)] == ["b"]
        store.log_request(str(uuid4()), "answered", {"retrieved_ids": ["b"]})
    finally:
        engine.dispose()
