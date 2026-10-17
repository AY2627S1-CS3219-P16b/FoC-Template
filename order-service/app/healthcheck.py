"""Container readiness probe while the HTTP endpoint handlers are unfinished."""

from urllib.request import urlopen

from sqlalchemy import text

from .database import create_database_engine


def main() -> None:
    with urlopen("http://127.0.0.1:8003/openapi.json", timeout=3) as response:
        response.read()
    engine = create_database_engine()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
