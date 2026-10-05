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
once Credit Service is added to `compose.yaml`. Paths below are relative to
`credit-service/` unless stated otherwise.

## File responsibilities

| File                    | Responsibility                                                   |
| ----------------------- | ---------------------------------------------------------------- |
| `app/main.py`           | FastAPI startup and HTTP endpoints                               |
| `app/api_schemas.py`    | Request and response models                                      |
| `app/credit_queries.py` | Atomic balance, reservation, transfer, and ledger operations     |
| `app/schema.py`         | Credit tables, constraints, and indexes                          |
| `app/auth.py`           | Verify callers through User Service JWTs                         |
| `tests/`                | Balance, reservation, transfer, idempotency, and API tests       |

## API

Interactive docs should run at <http://localhost:8002/docs> once the service is
wired into Docker Compose. Click **Authorize** and paste the access token
returned by User Service login, without the `Bearer` prefix.

### Authentication

Credit endpoints should require `Authorization: Bearer <access_token>`, obtained
from User Service login. Tokens are verified locally using User Service's public
key (`JWT_PUBLIC_KEY_PATH`). Credit Service should not hold the User Service
private key and should not need to call User Service for every request.

| Status | Meaning                                               |
| ------ | ----------------------------------------------------- |
| `401`  | Missing, invalid, expired, or inactive account token  |
| `403`  | Signed in, but not allowed to perform the operation   |
| `404`  | Account, order reservation, or ledger target missing  |
| `409`  | Insufficient credits, duplicate reservation, or invalid lifecycle transition |
| `422`  | Invalid request body or parameter                     |

### Expected endpoints

| Endpoint                                           | Purpose                                  | Who |
| -------------------------------------------------- | ---------------------------------------- | --- |
| `GET /health`                                      | Container and service health check       | any |
| `POST /api/v1/credits/me/initialize`               | Create the caller's initial credit account if missing | user |
| `GET /api/v1/credits/me`                           | Show caller's available and reserved balance | user |
| `GET /api/v1/credits/me/ledger`                    | Show caller's credit transaction history | user |
| `POST /api/v1/credits/reservations`                | Reserve credits for a new order          | requester or Order Service |
| `POST /api/v1/credits/reservations/{order_id}/release` | Release held credits after cancellation or expiry | requester or Order Service |
| `POST /api/v1/credits/reservations/{order_id}/transfer` | Transfer held credits to the courier after completion | requester or Order Service |

Order Service is the intended caller for lifecycle mutations once it exists. A
direct authenticated API is still useful for early development and testing.

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

Ledger entries are append-only records of credit movements. They should be
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

When a user registers, Credit Service should create a credit account with the
initial allocation, for example 20 available credits and 0 reserved credits.
This may be triggered directly by the frontend during early development, or by
an asynchronous user-created event once the event workflow is implemented.

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

Each mutation should run inside a single database transaction. This is how the
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

## Additional tables

The three schema tables are enough for the core project requirements. For the
asynchronous or event-driven requirement, add supporting tables only after the
team finalizes the event workflow.

Useful additions later:

| Table               | Purpose                                                       |
| ------------------- | ------------------------------------------------------------- |
| `processed_events`  | Remember consumed event ids so duplicate messages are ignored |
| `credit_outbox_events` | Store events to publish after a successful DB transaction  |

Those tables are integration infrastructure, not part of the core credit model.
Keeping them separate makes the credit balances and ledger easier to reason
about.
