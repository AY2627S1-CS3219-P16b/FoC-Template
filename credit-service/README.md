# Credit Service

Owns credit balances, order reservations and the credit ledger. Only Order
Service (and its worker) can move credits; users can only read their own
balance and history. How registration and orders reach this service is in the
[integration guide](../integration.md); setup is in the
[startup guide](../startup.md).

## API

Swagger: <http://localhost:8002/docs>

**Authentication.** User routes need a User Service access token
(`Authorization: Bearer <token>`), verified locally with the public key; the
token's `account_status` must be `ACTIVE`. Service routes need an
`X-Service-Key` header: `ORDER_SERVICE_KEY` for reservations,
`USER_SERVICE_KEY` for registration events. A user token cannot call service
routes.

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/credits/me` | user | Own available and reserved balance |
| POST | `/api/v1/credits/me/initialize` | user | Create the caller's account with the initial credits if it does not exist yet; repeat calls return the existing account |
| GET | `/api/v1/credits/me/ledger` | user | Own ledger entries (`page`, `page_size` ≤ 100) |
| POST | `/api/v1/credits/reservations` | Order Service | Reserve credits for an order (returns 201) |
| GET | `/api/v1/credits/reservations/{order_id}` | Order Service | Read a reservation, used to check what already happened before a retry |
| POST | `/api/v1/credits/reservations/{order_id}/release` | Order Service | Return reserved credits to the requester |
| POST | `/api/v1/credits/reservations/{order_id}/transfer` | Order Service | Pay reserved credits to the courier |
| POST | `/internal/events/user-registered` | User Service | Grant initial credits for a new user |
| GET | `/health` | anyone | Checks the database |

**Request bodies**

```jsonc
// POST /reservations
{"order_id": "...", "requester_user_id": "...", "amount": 1, "idempotency_key": "order:<id>:reserve"}
// POST /reservations/{order_id}/release
{"requester_user_id": "...", "idempotency_key": "order:<id>:release"}
// POST /reservations/{order_id}/transfer
{"requester_user_id": "...", "courier_user_id": "...", "idempotency_key": "order:<id>:transfer"}
// POST /internal/events/user-registered
{"event_id": "...", "type": "user.registered.v1", "user_id": "...", "occurred_at": "2026-11-10T08:00:00Z"}
```

Unknown fields are rejected. `amount` must be a positive integer.

**Repeated calls are safe.**

- Reserving again with the same order, requester and amount returns the existing reservation.
- Releasing an already released reservation, or transferring again to the same courier, returns the reservation unchanged.
- A registration event with a known `event_id` returns `"duplicate": true` and grants nothing.

## Errors

Errors use `{"detail": "..."}`.

| Status | When |
| --- | --- |
| 401 | Missing, invalid or expired token, or an inactive account ("Please log in with an active account.") |
| 403 | Missing or wrong `X-Service-Key` ("This operation requires an authorized service.") |
| 404 | No credit account yet ("Credit account has not been initialized."); reservation not found |
| 409 | Not enough available credits ("Insufficient available credits."); a different reservation already exists for the order; the reservation is in the wrong state (e.g. releasing a transferred one, transferring to a different courier, or the courier is the requester); any other database constraint violation |
| 422 | Invalid body or parameters |
| 503 | Database unavailable, or the service key is not configured on this service |

## Data model

```text
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

| Table | Columns | Notes |
| --- | --- | --- |
| `credit_accounts` | `user_id`, `available_balance`, `reserved_balance`, `created_at`, `updated_at` | One per user. Both balances have `CHECK >= 0`. |
| `credit_reservations` | `id`, `order_id`, `requester_user_id`, `courier_user_id`, `amount`, `status`, `created_at`, `updated_at` | `order_id` is unique. `status` is `RESERVED`, `RELEASED` or `TRANSFERRED`. `amount > 0`; the courier cannot be the requester. |
| `credit_ledger_entries` | `id`, `user_id`, `order_id`, `type`, `amount`, `available_balance_after`, `reserved_balance_after`, `reservation_id`, `idempotency_key`, `created_at` | Append-only history. `idempotency_key` is unique. Types: `INITIAL_ALLOCATION`, `CREDIT_RESERVED`, `CREDIT_RELEASED`, `CREDIT_TRANSFERRED_IN`, `CREDIT_TRANSFERRED_OUT`. Balances after each entry are `>= 0`. |
| `processed_events` | `event_id`, `user_id`, `processed_at` | Registration events already handled. |

Each operation updates the balances, the reservation and the ledger in one
transaction, with row locks on the accounts involved:

| Operation | Balances | Reservation | Ledger entries |
| --- | --- | --- | --- |
| Initial allocation | new account: `available = INITIAL_CREDITS` | — | `INITIAL_ALLOCATION` |
| Reserve | requester: `available − amount`, `reserved + amount` | created as `RESERVED` | `CREDIT_RESERVED` |
| Release | requester: `available + amount`, `reserved − amount` | `RESERVED → RELEASED` | `CREDIT_RELEASED` |
| Transfer | requester: `reserved − amount`; courier: `available + amount` | `RESERVED → TRANSFERRED` | `CREDIT_TRANSFERRED_OUT` (requester), `CREDIT_TRANSFERRED_IN` (courier) |

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL connection | required |
| `JWT_PUBLIC_KEY_PATH` (or `JWT_PUBLIC_KEY`) | User Service public key | required |
| `ORDER_SERVICE_KEY` | Key for reservation routes | required for those routes |
| `USER_SERVICE_KEY` | Key for registration events | required for that route |
| `INITIAL_CREDITS` | Credits granted to each new account | `20` |
