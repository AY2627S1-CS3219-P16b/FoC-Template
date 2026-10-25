"""FAQ-owned PostgreSQL tables and exact cosine search over the small corpus."""

from sqlalchemy import (
    JSON, Column, DateTime, Integer, MetaData, String, Table, Text,
    create_engine, delete, func, insert, select, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from .config import EMBEDDING_DIMENSIONS, EMBEDDING_PROFILE

metadata = MetaData()
faq_index = Table(
    "faq_index", metadata,
    Column("id", Integer, primary_key=True),
    Column("version", String(64), nullable=False),
    Column("embedding_profile", Text, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
faq_chunks = Table(
    "faq_chunks", metadata,
    Column("id", String(24), primary_key=True),
    Column("source_file", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("question", Text, nullable=False),
    Column("answer", Text, nullable=False),
    Column("version", String(64), nullable=False),
    Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
)
faq_requests = Table(
    "faq_requests", metadata,
    Column("request_id", String(36), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("outcome", String(40), nullable=False),
    Column("details", JSON().with_variant(JSONB(), "postgresql"), nullable=False),
)


class IndexNotReady(Exception):
    pass


def create_database(url):
    if not url.startswith("postgresql"):
        raise ValueError("DATABASE_URL must point to the FAQ PostgreSQL database.")
    return create_engine(url, pool_pre_ping=True, pool_size=4, max_overflow=2,
                         connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000"})


class Store:
    def __init__(self, engine):
        self.engine = engine

    def initialize(self):
        with self.engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            metadata.create_all(connection)

    def status(self, expected_version):
        with self.engine.connect() as connection:
            row = connection.execute(select(faq_index).where(faq_index.c.id == 1)).mappings().first()
            if not row:
                return False
            return row["version"] == expected_version and row["embedding_profile"] == EMBEDDING_PROFILE

    def replace_index(self, corpus, vectors):
        if len(vectors) != len(corpus.chunks):
            raise ValueError("Every FAQ chunk must have an embedding.")
        # Readers see either the entire old index or the entire new index.
        # Serialize concurrent indexers, without blocking ordinary retrieval.
        with self.engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(32198004)"))
            connection.execute(delete(faq_chunks))
            connection.execute(delete(faq_index))
            connection.execute(insert(faq_chunks), [
                {"id": chunk.id, "source_file": chunk.source_file, "title": chunk.title,
                 "question": chunk.question, "answer": chunk.answer,
                 "version": corpus.version, "embedding": vector}
                for chunk, vector in zip(corpus.chunks, vectors)
            ])
            connection.execute(insert(faq_index).values(
                id=1, version=corpus.version, embedding_profile=EMBEDDING_PROFILE,
            ))

    def retrieve(self, vector, expected_version, min_similarity, limit=4):
        distance = faq_chunks.c.embedding.cosine_distance(vector)
        with self.engine.connect() as connection:
            if not self._index_matches(connection, expected_version):
                raise IndexNotReady()
            rows = connection.execute(
                select(faq_chunks.c.id, faq_chunks.c.source_file, faq_chunks.c.title,
                       faq_chunks.c.question, faq_chunks.c.answer, (1 - distance).label("score"))
                .where(faq_chunks.c.version == expected_version)
                .order_by(distance).limit(limit)
            ).mappings().all()
        # Filtering by the version prevents mixing a concurrent index refresh
        # with the metadata snapshot checked above.
        if not rows:
            raise IndexNotReady()
        return [dict(row) for row in rows if row["score"] >= min_similarity]

    @staticmethod
    def _index_matches(connection, version):
        return connection.execute(select(faq_index.c.id).where(
            faq_index.c.id == 1, faq_index.c.version == version,
            faq_index.c.embedding_profile == EMBEDDING_PROFILE,
        )).scalar_one_or_none() is not None

    def log_request(self, request_id, outcome, details):
        with self.engine.begin() as connection:
            connection.execute(insert(faq_requests).values(
                request_id=request_id, outcome=outcome, details=details,
            ))
