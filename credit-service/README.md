# Credit Service

The Credit Service owns the closed credit economy for Friend on Campus. It keeps
each user's available and reserved credit balances, records the reservation tied
to each order, and writes an immutable ledger entry for every credit movement.
Credits cannot be bought, withdrawn, or exchanged for money; they only move
inside the platform when an errand is created, canceled, expired, or completed.

The schema is designed around the project workflow: a requester must have enough
available credits before creating an order, those credits are held while the
order is open or in progress, and the held credits are either released back to
the requester or transferred to the courier when the lifecycle ends.

For installation, environment variables, database startup, and running the
service alongside the rest of the application, follow the shared startup guide
in `startup.md`. Paths below are relative to
`credit-service/` unless stated otherwise.

## File responsibilities

| File                    | Responsibility                                                   |
| ----------------------- | ---------------------------------------------------------------- |
| `app/main.py`           | FastAPI startup and HTTP endpoints                               |
| `app/api_schemas.py`    | Request and response models                                      |
| `app/credit_queries.py` | Atomic balance, reservation, transfer, and ledger operations     |
| `app/schema.py`         | Credit tables, constraints, and indexes                          |
| `app/auth.py`           | Verify callers through User Service JWTs                         |
| `app/allocation.py`     | Registration message deduplication and allocation              |

## API

Interactive docs run at <http://localhost:8002/docs>. Click **Authorize** and paste the access token
returned by User Service login, without the `Bearer` prefix.

### Authentication

User-facing credit endpoints require `Authorization: Bearer <access_token>`, obtained
from User Service login. Tokens are verified locally using User Service's public
key (`JWT_PUBLIC_KEY_PATH`). Credit Service does not hold the User Service
private key and does not call User Service for every request.

| Status | Meaning                                               |
| ------ | ----------------------------------------------------- |
| `401`  | Missing, invalid, expired, or inactive account token  |
| `403`  | Signed in, but not allowed to perform the operation   |
| `404`  | Account, order reservation, or ledger target missing  |
| `409`  | Insufficient credits, duplicate reservation, or invalid lifecycle transition |
| `422`  | Invalid request body or parameter                     |

### Endpoints

| Endpoint                                           | Purpose                                  | Who |
| -------------------------------------------------- | ---------------------------------------- | --- |
| `GET /health`                                      | Container and service health check       | any |
| `POST /api/v1/credits/me/initialize`               | Create the caller's initial credit account if missing | user |
| `GET /api/v1/credits/me`                           | Show caller's available and reserved balance | user |
| `GET /api/v1/credits/me/ledger`                    | Show caller's credit transaction history | user |
| `POST /api/v1/credits/reservations`                | Reserve credits for a new order          | Order Service |
| `POST /api/v1/credits/reservations/{order_id}/release` | Release held credits after cancellation or expiry | Order Service |
| `POST /api/v1/credits/reservations/{order_id}/transfer` | Transfer held credits to the courier after completion | Order Service |

Lifecycle mutations require `X-Service-Key: <ORDER_SERVICE_KEY>` and
`requester_user_id` in the JSON body. Reserve also takes `order_id` and `amount`;
transfer also takes `courier_user_id`. Release now requires a JSON body.
`GET /api/v1/credits/reservations/{order_id}` uses the same service credential
and supports reconciliation after an uncertain response. User JWTs cannot mutate
reservations. Order Service must enforce order ownership, assigned courier and
valid order states before calling Credit Service.

`POST /internal/events/user-registered` accepts only `USER_SERVICE_KEY` in
`X-Service-Key`. Keep these two credentials distinct, out of the frontend and Git.

## Schema

`app/schema.py` defines three core tables. The model separates current balances
from order-specific reservations and from the audit ledger, so the service can
answer "what is my balance now?" quickly while still preserving the history of
how that balance was reached.

```
        ┌──────────────────────────┐
        │  credit_accounts         │
        │    user_id               │
        │    available_balance     │
        │    reserved_balance      │
        └─────────────┬────────────┘
                      │ user_id
        ┌─────────────▼────────────┐
        │  credit_ledger_entries   │
        │    user_id               │
        │    order_id              │
        │    reservation_id        │
        └─────────────▲────────────┘
                      │ reservation_id
        ┌─────────────┴────────────┐
        │  credit_reservations     │
        │    order_id              │
        │    requester_user_id     │
        │    courier_user_id       │
        └──────────────────────────┘
```

**`credit_accounts`**

| Column                     | Type        | Notes                                      |
| -------------------------- | ----------- | ------------------------------------------ |
| `user_id`                  | text        | primary key; User Service user id          |
| `available_balance`        | integer     | credits available for new orders           |
| `reserved_balance`         | integer     | credits held for active orders             |
| `created_at`, `updated_at` | timestamptz |                                            |

The account table stores the current state only. Both balances are constrained
to be non-negative. When a new account is initialized, `available_balance` should
start at the configured initial allocation, and `reserved_balance` should start
at zero.

**`credit_reservations`**

| Column                     | Type        | Notes                                                  |
| -------------------------- | ----------- | ------------------------------------------------------ |
| `id`                       | text        | primary key                                            |
| `order_id`                 | text        | unique; one credit reservation per order               |
| `requester_user_id`        | text        | user whose credits are reserved                        |
| `courier_user_id`          | text        | nullable until completion                              |
| `amount`                   | integer     | number of credits reserved                             |
| `status`                   | text        | `RESERVED`, `RELEASED`, or `TRANSFERRED`               |
| `created_at`, `updated_at` | timestamptz |                                                        |

`order_id` is unique so retries cannot create multiple reservations for the
same order. `amount` must be positive. `courier_user_id` is nullable because an
order can reserve credits before any courier accepts or completes it. When it is
present, it must be different from `requester_user_id`, matching the project
rule that requesters cannot fulfill their own errand.

The valid lifecycle is:

```text
RESERVED -> RELEASED
RESERVED -> TRANSFERRED
```

`RELEASED` is used when an order is canceled or expires before completion.
`TRANSFERRED` is used only after successful delivery confirmation.

**`credit_ledger_entries`**

| Column                     | Type        | Notes                                                  |
| -------------------------- | ----------- | ------------------------------------------------------ |
| `id`                       | text        | primary key                                            |
| `user_id`                  | text        | account owner affected by this ledger entry            |
| `order_id`                 | text        | nullable for system entries such as initial allocation |
| `type`                     | text        | type of credit movement                                |
| `amount`                   | integer     | signed amount for this user                            |
| `available_balance_after`  | integer     | available balance after the movement                   |
| `reserved_balance_after`   | integer     | reserved balance after the movement                    |
| `reservation_id`           | text        | related reservation, when applicable                   |
| `idempotency_key`          | text        | unique key for safe retries, when provided             |
| `created_at`               | timestamptz |                                                        |

Ledger entries are append-only records of credit movements. They are
written in the same transaction as the balance or reservation update they
describe.

Allowed ledger types:

| Type                      | Meaning                                                     |
| ------------------------- | ----------------------------------------------------------- |
| `INITIAL_ALLOCATION`      | Credits granted when the user's account is initialized      |
| `CREDIT_RESERVED`         | Credits moved from available to reserved for an order       |
| `CREDIT_RELEASED`         | Reserved credits returned to available after cancel/expiry  |
| `CREDIT_TRANSFERRED_OUT`  | Requester's reserved credits spent on a completed order     |
| `CREDIT_TRANSFERRED_IN`   | Courier receives credits for completing an order            |

`available_balance_after` and `reserved_balance_after` are constrained to be
non-negative. They make the ledger easier to inspect during demos and debugging
because each row shows the account state immediately after that movement.

## Credit lifecycle

Registration saves a `credit_outbox` message in the same User Service
transaction as the new user. The separate `user-credit-worker` delivers it to
Credit Service, which atomically saves its `processed_events` marker, account
and initial ledger entry. `INITIAL_CREDITS` defaults to **20**, enough for twenty
one-credit errands. Existing users retain their allocation after configuration
changes. Authenticated `/me/initialize` remains an idempotent recovery path for
older users or delayed events. Reservation and transfer never create accounts
for arbitrary user IDs.

When a requester creates an order, Credit Service should reserve the required
credits atomically:

```text
available_balance -= amount
reserved_balance += amount
reservation.status = RESERVED
ledger.type = CREDIT_RESERVED
```

If the order is canceled or expires before completion, the reservation is
released:

```text
available_balance += amount
reserved_balance -= amount
reservation.status = RELEASED
ledger.type = CREDIT_RELEASED
```

If the order is completed, the reservation is transferred:

```text
requester.reserved_balance -= amount
courier.available_balance += amount
reservation.status = TRANSFERRED
requester ledger.type = CREDIT_TRANSFERRED_OUT
courier ledger.type = CREDIT_TRANSFERRED_IN
```

Each mutation runs inside a single database transaction. This is how the
service satisfies the project requirement that credit reservation, release, and
transfer are atomic.

## Constraints and invariants

- Credit balances cannot be negative.
- Reservation amounts must be greater than zero.
- There is only one reservation per `order_id`.
- A reservation can only be `RESERVED`, `RELEASED`, or `TRANSFERRED`.
- A requester cannot transfer credits to themselves as courier.
- Ledger balance snapshots cannot be negative.
- Ledger `idempotency_key` values are unique when supplied, so callers can retry
  safely without double-writing credit movements.

## D3 integration and remaining work

PostgreSQL supports transactional balance/ledger updates, unique constraints and
row locks for concurrent spending. Balance reads use the account primary key;
ledger reads use the user/time index; reservations use unique `order_id`.
Total balance is derived as `available_balance + reserved_balance`, avoiding a
third balance that could drift. Reserved balance equals the sum of that user's
`RESERVED` reservations. Release preserves total; transfer preserves the combined
requester/courier total. Only initial allocation creates new credits.

Account insertion uses `ON CONFLICT DO NOTHING`, so concurrent initialization
creates one allocation. A transaction-scoped advisory lock serializes each order,
including its first reservation. Account row locks prevent overspending across
orders; transfer locks both accounts in user-ID order to avoid deadlocks.
Identical retries return the existing reservation. Changed amounts/requesters or
incompatible terminal states return 409. Reusing a ledger idempotency key for a
different operation also returns 409 and rolls back all balance changes.

### Asynchronous allocation

This is a message-based workflow over HTTP with a PostgreSQL transactional
outbox as its durable queue. It avoids blocking registration on Credit Service
availability without adding broker infrastructure. Delivery is at least once;
`event_id` deduplicates delivery and the unique account ID prevents repeated
allocation even with a different event ID. No ordering is needed between users.

Example payload produced at registration:

```json
{"event_id":"registration-event-uuid","type":"user.registered.v1","user_id":"user-uuid","occurred_at":"2026-10-16T00:00:00+00:00"}
```

The worker polls every second with a five-second HTTP timeout. Failed delivery
uses exponential backoff capped at 256 seconds, retaining every pending message.
If the worker dies after Credit commits but before acknowledgement, the next
attempt is a harmless duplicate. Database outages are retried. Worker logs show
event ID, attempt, success/failure and HTTP error status; Credit logs duplicate
processing. `credit_outbox` exposes `attempts`, `next_attempt_at`, `delivered_at`;
`processed_events` records successful consumption. Persistent failures need an
operator to fix credentials or service errors; messages are never discarded.

### Order Service integration

Order Service persists pending actions in its `credit_jobs` table and runs an
independent `order-worker` for delivery and reconciliation, using this contract:

| Trigger | Required sequence and recovery |
| --- | --- |
| Create | Persist a pending order/action; reserve credits; publish the order as open only after success. If creation is abandoned after reservation, retry release until acknowledged. |
| Cancel/expire | Persist cancellation/expiry with a pending release; retry release until acknowledged. |
| Complete | Persist completion with a pending transfer to the assigned courier; retry transfer until acknowledged. |
| Timeout/crash | Inspect the reservation by order ID and retry the same operation. Keep pending actions until acknowledged. |

Credit Service cannot decide whether an errand was actually completed, cancelled
or expired. It must not automatically release old reservations because delivery
may still be in progress. The frontend sends lifecycle actions to Order Service;
only its worker can reserve, release or transfer credits. User JWTs receive 403
on credit mutations. Order creation checks Supplier Service before persisting
its pickup snapshot. See [Order Service](../order-service/README.md) and the
[integration guide](../integration.md). Runtime verification remains pending.

### Demo checklist

1. Register two users, log in as each, and read `/api/v1/credits/me`: each gets
   20 available, zero reserved, with one `INITIAL_ALLOCATION` ledger entry.
2. As Order Service, reserve 7 credits with
   `{"order_id":"demo","requester_user_id":"REQUESTER_ID","amount":7}`.
   Requester balance becomes 13 available / 7 reserved. Repeat: no extra debit.
3. Transfer with `{"requester_user_id":"REQUESTER_ID","courier_user_id":"COURIER_ID"}`:
   requester becomes 13 / 0, courier becomes 27 / 0. Repeat: no extra transfer.
   For a different order, reserve then release to demonstrate cancellation/expiry.
4. Stop Credit Service, register another user, inspect pending outbox/logs, then
   restart Credit Service and observe eventual allocation. Replay the same
   message with User Service's credential: `duplicate: true`, no extra credits.
5. Show a user token receiving 403 on reservation mutations.

Run service API calls through Swagger at ports 8000 and 8002. Service keys are
entered as the `X-Service-Key` header in Credit Swagger.

### Containers and deployment

Credit uses `python:3.12-slim`, installs `requirements.txt`, and starts Uvicorn on
8002. The worker reuses the User Service image with its own startup command.
PostgreSQL uses the Docker Official Image `postgres:17`. Compose service names
provide internal DNS. `credit-db` joins only the private `credit-data` network
and has no host port unless the development override is used (port 5435); the
API port is bound to loopback for Swagger. The database password comes from
the root `.env`. Database
health checks gate startup, Credit's `/health` checks its database, and the worker
and Credit restart after process failure. Connection pools check stale connections.

Named database volumes survive stop/recreate; `down -v` deletes them. Startup's
`metadata.create_all` adds the two new message tables without modifying existing
tables. It is not a schema migration system: future column changes need explicit
migrations. No credit seed data is required. Public JWT keys are mounted read-only;
only User Service has the private key. Service credentials come from environment
variables. The existing Compose database passwords remain local-development
values; before claiming complete Part 4 compliance, externalize those passwords,
freeze dependency versions and demonstrate external/internal network isolation.
Order Service and its worker are configured in Compose. A full container demo
and team N2H scope/owners remain project-level D3 work. Container execution has
not been verified during this review.
