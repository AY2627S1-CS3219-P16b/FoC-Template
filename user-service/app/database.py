from pathlib import Path

from sqlalchemy import (
    Column,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    select,
    update,
)
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import IntegrityError


class DuplicateEmailError(Exception):
    """Raised when an email address is already present in the users table."""


metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", String, primary_key=True),
    Column("email", String, nullable=False, unique=True, index=True),
    Column("password_hash", String, nullable=False),
    Column("display_name", String, nullable=False),
    Column("contact_preference", String, nullable=True),
    Column("telegram_handle", String, nullable=True),
    Column("phone_number", String, nullable=True),
    Column("profile_picture_url", String, nullable=True),
    Column("auth_role", String, nullable=False, default="USER"),
    Column("active_role_mode", String, nullable=False, default="REQUESTER"),
    Column("account_status", String, nullable=False, default="ACTIVE"),
    Column("created_at", String, nullable=False),
)

profile_columns = (
    users.c.id,
    users.c.email,
    users.c.display_name,
    users.c.contact_preference,
    users.c.telegram_handle,
    users.c.phone_number,
    users.c.profile_picture_url,
    users.c.auth_role,
    users.c.active_role_mode,
    users.c.account_status,
    users.c.created_at,
)


class Database:
    """Database access for the user service."""

    def __init__(self, database_url: str) -> None:
        url = make_url(database_url)
        if url.get_backend_name() == "sqlite" and url.database not in (None, ":memory:"):
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)

        self.engine: Engine = create_engine(database_url)

    def initialize(self) -> None:
        metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()

    def create_user(self, user: dict[str, object]) -> dict[str, object]:
        try:
            with self.engine.begin() as connection:
                connection.execute(users.insert().values(**user))
                row = connection.execute(
                    select(*profile_columns).where(users.c.id == user["id"])
                ).one()
        except IntegrityError as error:
            raise DuplicateEmailError from error

        return dict(row._mapping)

    def find_user_by_email(self, email: str) -> dict[str, object] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(
                    users.c.id,
                    users.c.email,
                    users.c.password_hash,
                    users.c.display_name,
                    users.c.auth_role,
                    users.c.active_role_mode,
                    users.c.account_status,
                ).where(users.c.email == email)
            ).one_or_none()

        return dict(row._mapping) if row else None

    def find_user_profile(self, user_id: str) -> dict[str, object] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(*profile_columns).where(users.c.id == user_id)
            ).one_or_none()
        return dict(row._mapping) if row else None

    def update_user_profile(
        self, user_id: str, changes: dict[str, object]
    ) -> dict[str, object] | None:
        with self.engine.begin() as connection:
            result = connection.execute(
                update(users).where(users.c.id == user_id).values(**changes)
            )
            if result.rowcount == 0:
                return None
            row = connection.execute(
                select(*profile_columns).where(users.c.id == user_id)
            ).one()
        return dict(row._mapping)

    def update_account_status(self, email: str, account_status: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                update(users)
                .where(users.c.email == email)
                .values(account_status=account_status)
            )

    def count_users(self) -> int:
        with self.engine.connect() as connection:
            return connection.execute(
                select(func.count()).select_from(users)
            ).scalar_one()
