from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from .database import create_database_engine
from .schema import metadata


def create_app() -> FastAPI:
    engine = create_database_engine()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            # Creates missing tables; existing supplier records are preserved.
            metadata.create_all(engine)
            # Open a real connection at startup to verify PostgreSQL is available.
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            app.state.database = engine
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Friend on Campus Supplier Service", lifespan=lifespan)

    return app
