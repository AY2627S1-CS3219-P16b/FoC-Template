import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def create_database_engine() -> Engine:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env.dev")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
