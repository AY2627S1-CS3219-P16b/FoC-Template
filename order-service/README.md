# Order Service

Owns errands, courier assignments, acceptance deadlines, order history and the
credit jobs sent to Credit Service. How orders move credits is in the
[integration guide](../integration.md); setup is in the
[startup guide](../startup.md).

## API

Swagger: <http://localhost:8003/docs>

**Authentication.** Every route except `/health` needs a User Service access
token (`Authorization: Bearer <token>`), verified locally with the public key;
the token's `account_status` must be `ACTIVE`. The caller's ID and role mode
come from the token, never from the request body.

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/orders` | requester mode | Create an order; returns 202 while credits are reserved |
| GET | `/api/v1/orders` | any user | Browse orders (`status` defaults to `OPEN`; filters `supplier_id`, `page`, `page_size` ≤ 100) |
| GET | `/api/v1/orders/me` | any user | Own orders: `role=requester` or `courier`, `view=active`, `past` or `all`, optional `status` |
| GET | `/api/v1/orders/admin` | admin | All orders; filters `requester_user_id`, `status` |
| GET | `/api/v1/orders/{order_id}` | requester, assigned courier; anyone for an unexpired `OPEN` order | Order details |
| GET | `/api/v1/orders/{order_id}/history` | requester, assigned courier | Chronological history |
| POST | `/api/v1/orders/{order_id}/accept` | courier mode, not the requester | Take an `OPEN` order before its deadline |
| POST | `/api/v1/orders/{order_id}/unassign` | assigned courier | Give back an `ACCEPTED` errand; it returns to `OPEN` with the same deadline |
| POST | `/api/v1/orders/{order_id}/pickup` | assigned courier | `ACCEPTED` → `PICKED_UP` |
| POST | `/api/v1/orders/{order_id}/deliver` | assigned courier | `PICKED_UP` → `DELIVERED` |
| POST | `/api/v1/orders/{order_id}/confirm` | requester | Confirm receipt of a `DELIVERED` order; returns 202 while credits transfer |
| POST | `/api/v1/orders/{order_id}/cancel` | requester | Cancel an unassigned `OPEN` order; returns 202 while credits are released |
| GET | `/api/v1/orders/{order_id}/contact` | requester, assigned courier | The other party's name and preferred contact, while `ACCEPTED`, `PICKED_UP` or `DELIVERED` |
| POST | `/api/v1/orders/{order_id}/retry-credit` | admin | Retry a credit job that stopped after too many failures |
| GET | `/health` | anyone | Checks the database |

**Creating an order.** Send an `Idempotency-Key` header (1–200 characters) and:

```json
{
  "supplier_id": "<supplier UUID>",
  "item_description": "One coffee",
  "delivery_location": "COM2 lobby",
  "delivery_instructions": "Message when you arrive",
  "credit_amount": 1,
  "expires_at": "2026-11-10T18:30:00+08:00"
}
```

- `expires_at` is the acceptance deadline. It must be in the future and at most
  60 minutes away. If the supplier has a closing time, the deadline must be at
  least 10 minutes before it.
- The supplier must be active and open; its name and pickup details are copied
  into the order.
- Repeating the request with the same key returns the original order. Reusing
  the key with different details returns 409.

**Statuses**

```text
RESERVING → OPEN → ACCEPTED → PICKED_UP → DELIVERED → COMPLETING → COMPLETED
   │          │  ↖────────┘ give back (before pickup)
   │          ├→ CANCELLING → CANCELLED   (requester cancels)
   │          └→ EXPIRING   → EXPIRED     (deadline passes)
   └→ REJECTED                            (not enough credits)
```

The `-ING` states wait for Credit Service to confirm. `DELIVERED` becomes
`COMPLETING` when the requester confirms, or automatically after `AUTO_CONFIRM_RECEIPT_HOURS` (24 by default). A
courier can hold only one `ACCEPTED` or `PICKED_UP` order at a time.

## Errors

Errors use `{"detail": "..."}`.

| Status | When |
| --- | --- |
| 401 | Missing, invalid or expired token, or an inactive account ("Please log in with an active account.") |
| 403 | Wrong role mode ("Switch to requester mode…" / "Switch to courier mode…"); not the requester or assigned courier; requester accepting their own order; non-admin on admin routes; Supplier Service refused the lookup |
| 404 | Order or supplier not found |
| 409 | The order is in the wrong state for this action (e.g. "Order must be DELIVERED to move to COMPLETING."); the deadline has passed; the courier already has an active errand ("Finish your current errand before accepting another one."); supplier inactive or closed; idempotency key reused with different details; no failed credit job to retry |
| 422 | Invalid body or parameters, including a deadline more than 60 minutes away or too close to closing time |
| 502 | Supplier or User Service returned an invalid response |
| 503 | Database, Supplier Service or User Service unavailable |

## Data model

| Table | Columns | Notes |
| --- | --- | --- |
| `orders` | `id`, `requester_user_id`, `courier_user_id`, `supplier_id`, `supplier_name`, `pickup_location`, `item_description`, `delivery_location`, `delivery_instructions`, `credit_amount`, `status`, `expires_at`, `created_at`, `updated_at`, `credit_error`, `idempotency_key` | (`requester_user_id`, `idempotency_key`) is unique. `credit_amount > 0`; the courier cannot be the requester; a courier is set exactly in the assigned states. Partial unique index `uq_orders_active_courier` on `courier_user_id` where status is `ACCEPTED` or `PICKED_UP`. |
| `order_log` | `id`, `order_id`, `actor_user_id`, `action`, `outcome`, `previous_status`, `new_status`, `details`, `created_at` | Every change, written in the same transaction. `actor_user_id` is null for worker actions. |
| `credit_jobs` | `id`, `order_id`, `operation`, `attempts`, `next_attempt_at`, `completed_at`, `failed_at`, `last_error_code`, `created_at` | Outbox of `RESERVE`, `RELEASE` and `TRANSFER` operations; one per order and operation. |

## Background worker

`python -m app.worker` (the `order-worker` container) runs every second. It:

- sends due credit jobs to Credit Service, one at a time while holding the
  order's lock, after first reading the existing reservation; each operation
  uses the key `order:<order_id>:<operation>`;
- retries failures with exponential backoff (capped at 256 seconds); after
  `CREDIT_JOB_MAX_ATTEMPTS` failures it sets `failed_at` and `credit_error` and
  waits for an admin retry. Not enough credits rejects the order immediately;
- expires `OPEN` orders whose deadline has passed;
- auto-confirms `DELIVERED` orders after `AUTO_CONFIRM_RECEIPT_HOURS`.

## Configuration

| Variable | Used by | Default |
| --- | --- | --- |
| `DATABASE_URL` | API, worker | required |
| `JWT_PUBLIC_KEY_PATH` (or `JWT_PUBLIC_KEY`) | API | required |
| `SUPPLIER_SERVICE_URL` | API | `http://localhost:8001` |
| `USER_SERVICE_URL`, `ORDER_CONTACT_SERVICE_KEY` | API (contact lookup) | `http://localhost:8000`; key required |
| `CREDIT_SERVICE_URL`, `ORDER_SERVICE_KEY` | worker | `http://localhost:8002`; key required |
| `AUTO_CONFIRM_RECEIPT_HOURS` | API, worker | `24` |
| `CREDIT_JOB_MAX_ATTEMPTS` | worker | `10` |

## Upgrading an existing database

Tables are created on first start. A database created before the one-errand
limit and the credit retry limit needs this once, with the API and worker
stopped:

```bash
docker compose exec -T order-db psql -U order_service -d order_db -v ON_ERROR_STOP=1 < order-service/migrations/001_review_fixes.sql
```

It fails without changing anything if a courier already holds two active
errands; resolve those first.

## Tests

From `order-service/`:

```bash
pip install -r requirements.txt pytest httpx
python -m pytest tests
```

Set `ORDER_TEST_DATABASE_URL` to a disposable PostgreSQL database to also run
the lifecycle and concurrency tests; each test uses its own schema.
