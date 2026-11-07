"""Run against a disposable PostgreSQL database via ORDER_TEST_DATABASE_URL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from app import order_queries as q
from app.schema import credit_jobs, metadata, order_log, orders
from app.worker import deliver_one


@pytest.fixture
def engine():
    url = os.getenv("ORDER_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set ORDER_TEST_DATABASE_URL for PostgreSQL regression tests")
    admin = create_engine(url)
    schema = "test_" + uuid4().hex
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    db = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    metadata.create_all(db)
    try:
        yield db
    finally:
        db.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def seed(engine, status="OPEN", courier=None, age=0, expired=False):
    with engine.begin() as conn:
        now = conn.execute(select(func.clock_timestamp())).scalar_one()
        oid = str(uuid4())
        conn.execute(insert(orders).values(id=oid, requester_user_id="requester", courier_user_id=courier,
            supplier_id="shop", supplier_name="Shop", pickup_location="Lobby", item_description="Lunch",
            delivery_location="Library", credit_amount=1, status=status, idempotency_key=oid,
            created_at=now - timedelta(days=3), updated_at=now - timedelta(hours=age),
            expires_at=now + timedelta(hours=-1 if expired else 1)))
    return oid


def test_courier_limit_and_delivered_releases_slot(engine):
    first, second = seed(engine), seed(engine)
    with engine.begin() as conn:
        q.assign_courier(conn, first, courier_user_id="courier")
        assert q.assign_courier(conn, first, courier_user_id="courier")["status"] == "ACCEPTED"
    with pytest.raises(IntegrityError), engine.begin() as conn:
        q.assign_courier(conn, second, courier_user_id="courier")
    with engine.begin() as conn:
        q.mark_items_collected(conn, first, courier_user_id="courier")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        q.assign_courier(conn, second, courier_user_id="courier")
    with engine.begin() as conn:
        q.mark_delivery_completed(conn, first, courier_user_id="courier")
        q.assign_courier(conn, second, courier_user_id="courier")


def test_concurrent_accepts_only_one_succeeds(engine):
    ids = [seed(engine), seed(engine)]
    barrier = Barrier(2)
    def accept(oid):
        try:
            with engine.begin() as conn:
                barrier.wait(timeout=5)
                q.assign_courier(conn, oid, courier_user_id="courier")
            return True
        except IntegrityError:
            return False
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(accept, ids)) == [False, True]
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(order_log)).scalar_one() == 1


@pytest.mark.parametrize("expired", [False, True])
def test_unassign_preserves_deadline_and_credits(engine, expired):
    oid = seed(engine, "ACCEPTED", "courier", expired=expired)
    with engine.begin() as conn:
        before = conn.execute(select(orders).where(orders.c.id == oid)).mappings().one()
        with pytest.raises(q.OrderAccessDeniedError):
            q.unassign_courier(conn, oid, courier_user_id="stranger")
        after = q.unassign_courier(conn, oid, courier_user_id="courier")
        assert after["status"] == "OPEN" and after["courier_user_id"] is None
        assert after["expires_at"] == before["expires_at"]
        assert conn.execute(select(func.count()).select_from(credit_jobs)).scalar_one() == 0
        q.expire_open_orders(conn, now=conn.execute(select(func.clock_timestamp())).scalar_one())
        assert conn.execute(select(orders.c.status).where(orders.c.id == oid)).scalar_one() == ("EXPIRING" if expired else "OPEN")


def test_unassign_after_pickup_is_blocked(engine):
    oid = seed(engine, "PICKED_UP", "courier")
    with engine.begin() as conn, pytest.raises(q.OrderStateError):
        q.unassign_courier(conn, oid, courier_user_id="courier")


@pytest.mark.parametrize("status", ["OPEN", "ACCEPTED", "PICKED_UP", "DELIVERED", "COMPLETING", "COMPLETED", "CANCELLED", "EXPIRED"])
def test_contact_authorization(engine, status):
    courier = "courier" if status in {"ACCEPTED", "PICKED_UP", "DELIVERED", "COMPLETING", "COMPLETED"} else None
    oid = seed(engine, status, courier)
    with engine.begin() as conn:
        for user in ("requester", "courier", "stranger"):
            if status in {"ACCEPTED", "PICKED_UP", "DELIVERED"} and user != "stranger":
                assert q.get_contact_user_id(conn, oid, viewer_user_id=user) == ("courier" if user == "requester" else "requester")
            else:
                with pytest.raises(q.OrderAccessDeniedError):
                    q.get_contact_user_id(conn, oid, viewer_user_id=user)


def test_auto_confirmation_cutoff_idempotency_and_manual_race(engine):
    due = seed(engine, "DELIVERED", "courier", age=25)
    fresh = seed(engine, "DELIVERED", "courier", age=23)
    locked = seed(engine, "DELIVERED", "courier", age=25)
    with engine.begin() as holder:
        holder.execute(select(orders).where(orders.c.id == locked).with_for_update())
        with engine.begin() as conn:
            now = conn.execute(select(func.clock_timestamp())).scalar_one()
            q.auto_confirm_receipts(conn, now=now, window=timedelta(hours=24))
            q.auto_confirm_receipts(conn, now=now, window=timedelta(hours=24))
            assert conn.execute(select(orders.c.status).where(orders.c.id == fresh)).scalar_one() == "DELIVERED"
            assert conn.execute(select(orders.c.status).where(orders.c.id == locked)).scalar_one() == "DELIVERED"
            q.confirm_order_receipt(conn, due, requester_user_id="requester")
            assert conn.execute(select(func.count()).select_from(credit_jobs)).scalar_one() == 1
            log = conn.execute(select(order_log)).mappings().one()
            assert log["action"] == "AUTO_CONFIRM_RECEIPT" and log["actor_user_id"] is None


def test_exhausted_credit_job_is_visible_and_admin_retry_reconciles(engine):
    oid = seed(engine, "DELIVERED", "courier", age=25)
    with engine.begin() as conn:
        q.auto_confirm_receipts(conn, now=conn.execute(select(func.clock_timestamp())).scalar_one(), window=timedelta(hours=24))
    class Client:
        fail = True
        def apply(self, job):
            if self.fail:
                raise RuntimeError("mismatch")
    client = Client()
    assert deliver_one(engine, client, max_attempts=1)
    assert not deliver_one(engine, client, max_attempts=1)
    with engine.begin() as conn:
        job = dict(conn.execute(select(credit_jobs)).mappings().one())
        assert job["failed_at"] and job["attempts"] == 1 and not job["completed_at"]
        order = conn.execute(select(orders)).mappings().one()
        assert order["credit_error"] == "RuntimeError" and order["status"] == "COMPLETING"
        q.retry_failed_credit(conn, oid, actor_user_id="admin")
        retried = conn.execute(select(credit_jobs)).mappings().one()
        assert retried["id"] == job["id"] and retried["attempts"] == 0
    client.fail = False
    assert deliver_one(engine, client)
    with engine.connect() as conn:
        order = conn.execute(select(orders)).mappings().one()
        assert order["status"] == "COMPLETED" and order["credit_error"] is None


def test_temporary_failure_retries_before_limit(engine):
    oid = seed(engine, "DELIVERED", "courier", age=25)
    with engine.begin() as conn:
        q.auto_confirm_receipts(conn, now=conn.execute(select(func.clock_timestamp())).scalar_one(), window=timedelta(hours=24))
    class Offline:
        def apply(self, job):
            raise TimeoutError()
    deliver_one(engine, Offline(), max_attempts=2)
    with engine.connect() as conn:
        job = conn.execute(select(credit_jobs)).mappings().one()
        assert job["attempts"] == 1 and not job["failed_at"]
        assert job["next_attempt_at"] > job["created_at"]


def test_http_conflict_contact_and_admin_retry_permissions(engine):
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from app.auth import CurrentUser, current_user
    from app.main import create_app
    first, second = seed(engine), seed(engine)
    with engine.begin() as conn:
        q.assign_courier(conn, first, courier_user_id="courier")
    with patch("app.main.create_database_engine", return_value=engine), patch("app.main.load_jwt_public_key"):
        app = create_app()
    def caller(uid, role="USER"):
        app.dependency_overrides[current_user] = lambda: CurrentUser(
            id=uid, auth_role=role, active_role_mode="COURIER", account_status="ACTIVE")
    with TestClient(app) as client, patch.dict(os.environ, {"ORDER_CONTACT_SERVICE_KEY": "secret"}), patch("app.main.user_contact") as lookup:
        caller("courier")
        response = client.post(f"/api/v1/orders/{second}/accept")
        assert response.status_code == 409
        assert response.json()["detail"] == "Finish your current errand before accepting another one."
        lookup.return_value = {"display_name": "Name", "contact_preference": "TELEGRAM", "contact": "@name"}
        for user, other in (("requester", "courier"), ("courier", "requester")):
            caller(user)
            assert client.get(f"/api/v1/orders/{first}/contact").json() == lookup.return_value
            assert lookup.call_args.args[1] == other
        lookup.reset_mock()
        caller("stranger")
        assert client.get(f"/api/v1/orders/{first}/contact").status_code == 403
        assert client.post(f"/api/v1/orders/{first}/retry-credit").status_code == 403
        lookup.assert_not_called()
        caller("admin", "ADMIN")
        assert client.post(f"/api/v1/orders/{first}/retry-credit").status_code == 409


def test_retry_reconciles_previous_remote_commit_without_second_transfer():
    from unittest.mock import patch
    from app.service_clients import CreditClient, _Reservation
    client = CreditClient("http://credit", "key")
    job = {"order_id": "order", "operation": "TRANSFER", "order_status": "COMPLETING",
           "requester_user_id": "requester", "courier_user_id": "courier", "credit_amount": 1}
    reservation = _Reservation(order_id="order", requester_user_id="requester", courier_user_id="courier", amount=1, status="TRANSFERRED")
    with patch.object(client, "_request", return_value=reservation) as request:
        client.apply(job)
        request.assert_called_once_with("http://credit/api/v1/credits/reservations/order")


def test_migration_upgrades_existing_tables_and_can_be_reapplied(engine):
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[1] / "migrations/001_review_fixes.sql").read_text()
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX uq_orders_active_courier"))
        conn.execute(text("ALTER TABLE orders DROP COLUMN credit_error"))
        conn.execute(text("ALTER TABLE credit_jobs DROP COLUMN failed_at"))
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.exec_driver_sql(sql)
        conn.exec_driver_sql(sql)
        conn.execute(select(orders.c.credit_error))
        conn.execute(select(credit_jobs.c.failed_at))
    first, second = seed(engine), seed(engine)
    with engine.begin() as conn:
        q.assign_courier(conn, first, courier_user_id="courier")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        q.assign_courier(conn, second, courier_user_id="courier")
