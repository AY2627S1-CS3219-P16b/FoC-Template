BEGIN;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS credit_error VARCHAR(100);
ALTER TABLE credit_jobs ADD COLUMN IF NOT EXISTS failed_at TIMESTAMPTZ;
-- Resolve any existing duplicate active courier assignments before applying.
-- A conflict aborts the transaction without changing assignments or balances.
CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_active_courier
ON orders (courier_user_id) WHERE status IN ('ACCEPTED', 'PICKED_UP');
COMMIT;
