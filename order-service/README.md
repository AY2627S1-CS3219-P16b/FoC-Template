# Order Service

Owns errands, courier assignments, acceptance deadlines, order history, and
durable credit actions. User Service owns authentication; Supplier Service owns
supplier availability and pickup details; Credit Service owns all balances.

## API

Swagger: <http://localhost:8003/docs>. All order endpoints require a User Service
JWT. `/health` is public and checks PostgreSQL connectivity.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/orders` | Create a request pending credit reservation |
| GET | `/api/v1/orders` | Browse visible orders; status defaults to `OPEN` |
| GET | `/api/v1/orders/me?role=requester` | My requests; `role=courier` lists my assignments |
| GET | `/api/v1/orders/{order_id}` | Current order details |
| POST | `/api/v1/orders/{order_id}/accept` | Assign the calling courier |
| POST | `/api/v1/orders/{order_id}/pickup` | Assigned courier marks collection |
| POST | `/api/v1/orders/{order_id}/deliver` | Assigned courier marks delivery |
| POST | `/api/v1/orders/{order_id}/confirm` | Requester confirms receipt; queue payment |
| POST | `/api/v1/orders/{order_id}/cancel` | Requester cancels an open order; queue release |
| GET | `/api/v1/orders/{order_id}/history` | Participants read chronological history |
| GET | `/health` | Application and database readiness |

Creation requires `Idempotency-Key` (1–200 characters) and this JSON body:

```json
{
  "supplier_id": "00000000-0000-4000-8000-000000000001",
  "item_description": "One coffee",
  "delivery_location": "COM2 lobby",
  "delivery_instructions": "Message when you arrive",
  "credit_amount": 3,
  "expires_at": "2030-01-01T18:00:00+08:00"
}
```

Use an actual supplier ID and a future acceptance deadline. The requester ID
comes from the JWT; supplier name and pickup details come from Supplier Service.
Inactive or closed suppliers cannot receive new requests. Supplier edits do not
rewrite existing orders. Identical creation retries return the original order;
reusing a key with changed client fields returns 409.

Creation and pending cancel/confirm actions return 202. Poll order details until
the pending state resolves. Lists support `page` and `page_size` (maximum 100);
order lists also support `status`, and browsing supports `supplier_id`.
Unexpired open orders are visible to authenticated users. Other orders and
history are limited to their requester and assigned courier.

Errors: 401 for invalid credentials, 403 for unauthorized actions, 404 for missing
orders, 409 for lifecycle/idempotency conflicts, 422 for invalid input, 502 for
invalid upstream responses, and 503 for unavailable dependencies. Token account
status is verified locally and reflects the token's claims until it expires.

## Lifecycle and recovery

```text
RESERVING → OPEN → ACCEPTED → PICKED_UP → DELIVERED → COMPLETING → COMPLETED
              ↘ CANCELLING → CANCELLED
              ↘ EXPIRING → EXPIRED
RESERVING → REJECTED  (insufficient credits)
```

Only the requester can cancel or confirm; requesters cannot accept their own
orders. Courier mode is required for acceptance. Assigned couriers can continue
their existing assignment after switching mode. Retries of successful actions
return the current order without regressing state or duplicating history.

Each mutation writes its order change, history and any credit job in one database
transaction. Row locks serialize acceptance against cancellation and expiry.
Expiry applies only to unassigned `OPEN` orders; the deadline is for acceptance,
not for finishing a delivery. A delayed reservation that succeeds after its
deadline moves straight to `EXPIRING` and queues release without publishing open.

`python -m app.worker` runs the independent expiry/credit worker. Due jobs are
claimed with order row locks and `SKIP LOCKED`, one per transaction. The worker
checks Credit Service's reservation before each action, verifies the order,
requester, amount and recipient, and uses a stable key per order/operation.
Timeouts and crashes after a remote commit are reconciled on the next attempt.
Only acknowledged credit movements finalize order states. Missing credit
accounts are retried while registration allocation catches up. Only a definitive
insufficient-funds response rejects a reservation; configuration and incompatible
reservation errors stay queued for operator attention.

Retries use exponential backoff capped at 256 seconds. Inspect `credit_jobs`
(`attempts`, `last_error_code`, `next_attempt_at`, `completed_at`) and worker logs
for failures. Pending jobs are retained through restarts. Logs identify jobs and
error types/statuses without printing service credentials.

## Containers and local setup

See [startup guide](../startup.md). Compose starts `order-db`, `order-service` and
`order-worker`. The API runs as a non-root user on port 8003; PostgreSQL
persists in `order-db-data` and is reachable only on the private `order-data`
network, or on host port 5436 with the development override. The worker needs
no JWT key. Only the API receives User Service's read-only public key.

For a Python setup, use Python 3.12 and install `requirements.txt`. Start
`order-db` with the development override so port 5436 is published:

```sh
docker compose -f compose.yaml -f compose.dev.yaml up -d order-db
```

Configure `order-service/.env.dev` (or environment variables), using
`ORDER_DB_PASSWORD` from the root `.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://order_service:<ORDER_DB_PASSWORD>@localhost:5436/order_db
JWT_PUBLIC_KEY_PATH=../user-service/keys/jwt-public.pem
SUPPLIER_SERVICE_URL=http://localhost:8001
CREDIT_SERVICE_URL=http://localhost:8002
ORDER_SERVICE_KEY=<same secret configured in Credit Service>
```

From `order-service/`, run the API and worker in separate terminals:

```sh
python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8003
python -m app.worker
```

Start the API first so its startup creates the tables. `create_all` creates
missing tables; it does not migrate existing columns or constraints. Database
credentials in Compose are for local development. No initial order data is needed.

## Verification limits

The repository does not contain the full assignment rubric. This implementation
follows the lifecycle and Credit/Supplier contracts in this repository. Runtime
verification and container builds were not performed during this review, as
requested. The frontend calls Order Service for lifecycle actions and polls
orders and credits immediately after actions, every second while credit actions
are pending, and every five seconds otherwise. It does not hold service credentials.
