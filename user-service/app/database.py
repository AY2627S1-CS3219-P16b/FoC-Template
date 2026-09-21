from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    select,
    update,
)
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import IntegrityError


class DuplicateEmailError(Exception):
    """Raised when an email address is already present in the users table."""


class AdminPermissionError(Exception):
    """The actor is not currently an active admin, or targets themselves."""


class UserNotFoundError(Exception):
    """The target account does not exist."""


class LastActiveAdminError(Exception):
    """A change would leave no active admin account."""


class NoChangeError(Exception):
    """The requested role or status already has that value."""


class BootstrapUnavailableError(Exception):
    """Bootstrap targets another account or the initial candidate is ineligible."""


@dataclass(frozen=True)
class BootstrapResult:
    user: dict[str, object]
    created: bool


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

admin_audit_logs = Table(
    "admin_audit_logs",
    metadata,
    Column("id", String, primary_key=True),
    Column("acting_admin_user_id", String, ForeignKey("users.id"), nullable=False),
    Column("target_user_id", String, ForeignKey("users.id"), nullable=False),
    Column("action_type", String, nullable=False),
    Column("previous_value", JSON, nullable=False),
    Column("new_value", JSON, nullable=False),
    Column("reason", String, nullable=False),
    Column("timestamp", String, nullable=False),
)

admin_bootstrap = Table(
    "admin_bootstrap",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", String, ForeignKey("users.id"), nullable=False),
    Column("timestamp", String, nullable=False),
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

    def update_active_role_mode(
        self, user_id: str, role_mode: str
    ) -> dict[str, object] | None:
        with self.engine.begin() as connection:
            result = connection.execute(
                update(users)
                .where(users.c.id == user_id, users.c.account_status == "ACTIVE")
                .values(active_role_mode=role_mode)
            )
            if result.rowcount == 0:
                return None
            row = connection.execute(
                select(*profile_columns).where(users.c.id == user_id)
            ).one()
        return dict(row._mapping)

    def list_user_profiles(self) -> list[dict[str, object]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(*profile_columns).order_by(users.c.created_at, users.c.id)
            ).all()
        return [dict(row._mapping) for row in rows]

    def list_admin_audit_logs(self) -> list[dict[str, object]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(admin_audit_logs).order_by(
                    admin_audit_logs.c.timestamp, admin_audit_logs.c.id
                )
            ).all()
        return [dict(row._mapping) for row in rows]

    def admin_audit_page(self, page: int, page_size: int) -> dict[str, object]:
        actor = users.alias("actor")
        target = users.alias("target")
        with self.engine.connect() as connection:
            total = connection.execute(
                select(func.count()).select_from(admin_audit_logs)
            ).scalar_one()
            rows = connection.execute(
                select(
                    admin_audit_logs,
                    actor.c.display_name.label("acting_admin_display_name"),
                    actor.c.email.label("acting_admin_email"),
                    target.c.display_name.label("target_display_name"),
                    target.c.email.label("target_email"),
                )
                .join(actor, actor.c.id == admin_audit_logs.c.acting_admin_user_id)
                .join(target, target.c.id == admin_audit_logs.c.target_user_id)
                .order_by(admin_audit_logs.c.timestamp.desc(), admin_audit_logs.c.id.desc())
                .limit(page_size)
                .offset((page - 1) * page_size)
            ).all()
        return {
            "items": [dict(row._mapping) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def _lock_active_admins(self, connection: Connection) -> None:
        if self.engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.execute(
                select(users.c.id)
                .where(users.c.auth_role == "ADMIN", users.c.account_status == "ACTIVE")
                .order_by(users.c.id)
                .with_for_update()
            ).all()

    def _require_admin(self, connection: Connection, actor_id: str) -> None:
        actor = connection.execute(
            select(users.c.auth_role, users.c.account_status).where(users.c.id == actor_id)
        ).one_or_none()
        if not actor or actor.auth_role != "ADMIN" or actor.account_status != "ACTIVE":
            raise AdminPermissionError

    def _profile(self, connection: Connection, user_id: str) -> dict[str, object]:
        row = connection.execute(
            select(*profile_columns).where(users.c.id == user_id)
        ).one_or_none()
        if not row:
            raise UserNotFoundError
        return dict(row._mapping)

    def _record_admin_change(
        self,
        connection: Connection,
        actor_id: str,
        target_id: str,
        action_type: str,
        previous_value: dict[str, object],
        new_value: dict[str, object],
        reason: str,
    ) -> None:
        connection.execute(admin_audit_logs.insert().values(
            id=str(uuid4()),
            acting_admin_user_id=actor_id,
            target_user_id=target_id,
            action_type=action_type,
            previous_value=previous_value,
            new_value=new_value,
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

    def admin_update_profile(
        self, actor_id: str, target_id: str, changes: dict[str, object], reason: str
    ) -> dict[str, object]:
        with self.engine.begin() as connection:
            self._lock_active_admins(connection)
            self._require_admin(connection, actor_id)
            if actor_id == target_id:
                raise AdminPermissionError
            target = self._profile(connection, target_id)
            changed = {key: value for key, value in changes.items() if target[key] != value}
            if changed:
                previous = {key: target[key] for key in changed}
                connection.execute(
                    update(users).where(users.c.id == target_id).values(**changed)
                )
                self._record_admin_change(
                    connection, actor_id, target_id, "PROFILE_UPDATED",
                    previous, changed, reason,
                )
            return self._profile(connection, target_id)

    def change_auth_role(
        self, actor_id: str, target_id: str, auth_role: str, reason: str
    ) -> dict[str, object]:
        with self.engine.begin() as connection:
            self._lock_active_admins(connection)
            self._require_admin(connection, actor_id)
            if actor_id == target_id:
                raise AdminPermissionError
            target = self._profile(connection, target_id)
            previous_role = target["auth_role"]
            if previous_role == auth_role:
                raise NoChangeError
            if auth_role == "USER" and target["account_status"] == "ACTIVE":
                remaining = connection.execute(
                    select(func.count()).select_from(users).where(
                        users.c.auth_role == "ADMIN",
                        users.c.account_status == "ACTIVE",
                        users.c.id != target_id,
                    )
                ).scalar_one()
                if remaining == 0:
                    raise LastActiveAdminError
            connection.execute(
                update(users).where(users.c.id == target_id).values(auth_role=auth_role)
            )
            self._record_admin_change(
                connection, actor_id, target_id, "AUTH_ROLE_CHANGED",
                {"auth_role": previous_role}, {"auth_role": auth_role}, reason,
            )
            return self._profile(connection, target_id)

    def change_account_status(
        self, actor_id: str, target_id: str, account_status: str, reason: str
    ) -> dict[str, object]:
        with self.engine.begin() as connection:
            self._lock_active_admins(connection)
            self._require_admin(connection, actor_id)
            if actor_id == target_id:
                raise AdminPermissionError
            target = self._profile(connection, target_id)
            previous_status = target["account_status"]
            if previous_status == account_status:
                raise NoChangeError
            if target["auth_role"] == "ADMIN" and previous_status == "ACTIVE":
                remaining = connection.execute(
                    select(func.count()).select_from(users).where(
                        users.c.auth_role == "ADMIN",
                        users.c.account_status == "ACTIVE",
                        users.c.id != target_id,
                    )
                ).scalar_one()
                if remaining == 0:
                    raise LastActiveAdminError
            connection.execute(
                update(users).where(users.c.id == target_id)
                .values(account_status=account_status)
            )
            self._record_admin_change(
                connection, actor_id, target_id, "ACCOUNT_STATUS_CHANGED",
                {"account_status": previous_status},
                {"account_status": account_status}, reason,
            )
            return self._profile(connection, target_id)

    def bootstrap_first_admin(self, email: str) -> BootstrapResult:
        try:
            with self.engine.begin() as connection:
                if self.engine.dialect.name == "sqlite":
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                bootstrap = connection.execute(
                    select(admin_bootstrap.c.user_id).where(admin_bootstrap.c.id == 1)
                ).one_or_none()
                candidate = connection.execute(
                    select(users.c.id, users.c.auth_role, users.c.account_status)
                    .where(users.c.email == email)
                ).one_or_none()
                if bootstrap:
                    if not candidate or candidate.id != bootstrap.user_id:
                        raise BootstrapUnavailableError
                    return BootstrapResult(self._profile(connection, candidate.id), False)

                existing_admin = connection.execute(
                    select(users.c.id).where(users.c.auth_role == "ADMIN").limit(1)
                ).one_or_none()
                if existing_admin or not candidate or candidate.auth_role != "USER" or candidate.account_status != "ACTIVE":
                    raise BootstrapUnavailableError
                connection.execute(admin_bootstrap.insert().values(
                    id=1,
                    user_id=candidate.id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ))
                result = connection.execute(
                    update(users)
                    .where(
                        users.c.id == candidate.id,
                        users.c.auth_role == "USER",
                        users.c.account_status == "ACTIVE",
                    )
                    .values(auth_role="ADMIN")
                )
                if result.rowcount != 1:
                    raise BootstrapUnavailableError
                return BootstrapResult(self._profile(connection, candidate.id), True)
        except IntegrityError as error:
            with self.engine.connect() as connection:
                bootstrap = connection.execute(
                    select(admin_bootstrap.c.user_id).where(admin_bootstrap.c.id == 1)
                ).one_or_none()
                candidate = connection.execute(
                    select(users.c.id).where(users.c.email == email)
                ).one_or_none()
                if bootstrap and candidate and bootstrap.user_id == candidate.id:
                    return BootstrapResult(self._profile(connection, candidate.id), False)
            raise BootstrapUnavailableError from error

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
