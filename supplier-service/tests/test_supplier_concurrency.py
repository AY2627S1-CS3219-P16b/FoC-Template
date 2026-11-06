"""Real PostgreSQL regressions for competing supplier changes and audit history."""

import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import time as daytime
from queue import Queue
from uuid import uuid4

from sqlalchemy import select, text

from app.admin_queries import NoChangeError, deactivate_supplier, update_supplier
from app.database import create_database_engine
from app.schema import create_schema, places, supplier_audit_logs, suppliers


@unittest.skipUnless(os.getenv("RUN_POSTGRES_TESTS") == "1",
                     "Set RUN_POSTGRES_TESTS=1 for PostgreSQL checks")
class SupplierConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine()
        self.schema = "supplier_concurrency_" + uuid4().hex
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.addCleanup(self.drop_schema)
        self.db = self.engine.execution_options(schema_translate_map={None: self.schema})
        self.supplier_id = uuid4()
        self.actor_id = uuid4()
        with self.db.begin() as connection:
            create_schema(connection)
            place_id = uuid4()
            connection.execute(places.insert().values(id=place_id, name="Test Place"))
            connection.execute(suppliers.insert().values(
                id=self.supplier_id, name="Cafe A", supplier_type="FOOD_BEVERAGE",
                place_id=place_id, opening_time=daytime(8), closing_time=daytime(18),
                operating_days=["MON"],
            ))

    def drop_schema(self):
        with self.engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))

    def change(self, connection, operation, **kwargs):
        return operation(connection, actor_id=self.actor_id,
                         supplier_id=self.supplier_id, reason="concurrency test", **kwargs)

    def competing_changes(self, first_operation, second_operation):
        """Hold the first change uncommitted until PostgreSQL reports the second waits.

        Observing the actual database lock avoids assuming a thread has reached
        its query after an arbitrary sleep. Both the fixed and old code block,
        but only the fixed code reads previous values after that wait.
        """
        backend_ids = Queue()

        def second_change():
            with self.db.begin() as connection:
                connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                backend_ids.put(connection.scalar(text("SELECT pg_backend_pid()")))
                return second_operation(connection)

        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.db.begin() as first:
                first_operation(first)
                first_pid = first.scalar(text("SELECT pg_backend_pid()"))
                future = executor.submit(second_change)
                second_pid = backend_ids.get(timeout=5)
                deadline = time.monotonic() + 3
                with self.engine.connect() as observer:
                    while True:
                        blockers = observer.scalar(
                            text("SELECT pg_blocking_pids(:pid)"), {"pid": second_pid},
                        )
                        if first_pid in blockers:
                            break
                        if future.done():
                            future.result()  # Surface a worker failure before timing out.
                        self.assertLess(time.monotonic(), deadline,
                                        "Second supplier change did not wait for the first")
                        time.sleep(0.01)
            # The first transaction commits before waiting for the second.
            return future.result(timeout=5)

    def audit_rows(self):
        with self.db.connect() as connection:
            return list(connection.execute(select(supplier_audit_logs).order_by(
                supplier_audit_logs.c.created_at, supplier_audit_logs.c.id,
            )).mappings())

    def test_competing_renames_record_the_value_actually_replaced(self):
        result = self.competing_changes(
            lambda connection: self.change(connection, update_supplier,
                                           changes={"name": "Cafe B"}),
            lambda connection: self.change(connection, update_supplier,
                                           changes={"name": "Cafe C"}),
        )
        self.assertEqual(result["name"], "Cafe C")
        rows = self.audit_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["previous_value"], {"name": "Cafe A"})
        self.assertEqual(rows[0]["new_value"], {"name": "Cafe B"})
        self.assertEqual(rows[1]["previous_value"], {"name": "Cafe B"})
        self.assertEqual(rows[1]["new_value"], {"name": "Cafe C"})

    def test_competing_deactivations_do_not_duplicate_the_audit_entry(self):
        with self.assertRaises(NoChangeError):
            self.competing_changes(
                lambda connection: self.change(connection, deactivate_supplier),
                lambda connection: self.change(connection, deactivate_supplier),
            )
        rows = self.audit_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action_type"], "SUPPLIER_DEACTIVATED")
        self.assertEqual(rows[0]["previous_value"], {"is_active": True})
        self.assertEqual(rows[0]["new_value"], {"is_active": False})

    def test_restore_waits_for_deactivation_and_reads_inactive_state(self):
        result = self.competing_changes(
            lambda connection: self.change(connection, deactivate_supplier),
            lambda connection: self.change(connection, update_supplier,
                                           changes={"is_active": True}),
        )
        self.assertTrue(result["is_active"])
        rows = self.audit_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["previous_value"], {"is_active": False})
        self.assertEqual(rows[1]["new_value"], {"is_active": True})
