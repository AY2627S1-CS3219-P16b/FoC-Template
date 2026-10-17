# Service integration

| Service | Owns | Integration |
| --- | --- | --- |
| User (`8000`) | Accounts, roles, JWT signing | Registration outbox delivers initial-credit events to Credit Service |
| Supplier (`8001`) | Catalogue, campus locations, opening hours | Order Service fetches supplier details using the caller's JWT |
| Credit (`8002`) | Available/reserved balances, reservations, immutable ledger | Accepts order mutations only with `ORDER_SERVICE_KEY` |
| Order (`8003`) | Errands, assignments, history, credit jobs | Worker reserves/releases/transfers credits and expires unaccepted orders |

Each service has its own PostgreSQL database. Services use HTTP contracts and
shared IDs; they do not read each other's tables. Only User Service receives the
private JWT key. Other APIs verify its tokens locally with the public key.
Role switching returns a fresh `access_token` alongside the updated user profile;
the frontend replaces its token so Order Service sees the new role immediately.

## Registration and initial credits

User Service commits the user and registration event in one transaction.
`user-credit-worker` sends that event to Credit Service with `USER_SERVICE_KEY`.
Credit Service deduplicates event delivery and initializes one account, with
20 credits by default. `/credits/me/initialize` is an authenticated recovery
path and cannot allocate a second balance. Registration does not block on Credit.

## Creating an errand

The frontend lists real suppliers from Supplier Service and sends a selected
supplier ID, request details, acceptance deadline, reward and `Idempotency-Key`
to `POST /api/v1/orders`. The requester is taken from the JWT. Order Service
checks the supplier's activity/opening status and records a pickup snapshot.
It atomically saves a `RESERVING` order, history entry and `RESERVE` job.

`order-worker` sends this body to Credit Service using `X-Service-Key`:

```json
{
  "order_id": "<persisted order UUID>",
  "requester_user_id": "<JWT subject>",
  "amount": 1,
  "idempotency_key": "order:<order UUID>:reserve"
}
```

Only an acknowledged reservation makes the order `OPEN`. Insufficient funds
make it `REJECTED`. Missing accounts and dependency failures are retried. If
reservation succeeds after the deadline, the order moves to `EXPIRING` and queues
release without becoming available for acceptance.

## Delivery, cancellation and expiry

The courier accepts, picks up and marks delivery through Order Service. The
requester confirms receipt. Order Service then queues a `TRANSFER` using the
persisted requester, assigned courier and reward; the frontend supplies no
recipient or transfer amount. After acknowledgement, the order is `COMPLETED`.

Canceling an unassigned open order queues `RELEASE`; automatic expiry does the
same for unaccepted orders. Only release acknowledgement finalizes `CANCELLED`
or `EXPIRED`. Row locks prevent acceptance from racing cancellation or expiry.

The worker inspects reservations by order ID before retrying, validates their
identity/amount/recipient, and uses stable per-operation keys. A crash after a
credit commit can therefore recover without spending or paying twice. Pending
jobs persist, use bounded exponential backoff, and remain visible for operator
attention if credentials or data need fixing.

## Frontend and containers

The frontend calls only user-authorized routes and reads balances/ledger directly
from Credit Service. It never holds service keys or calls reservation mutations.
Orders are persisted by the server, and order states and balances are refreshed
every five seconds while signed in. Pending states are displayed until workers
finish; the UI does not claim completion before credit acknowledgement.

Compose starts all four APIs/databases plus `user-credit-worker` and
`order-worker`. Vite routes `/api/v1/orders` to Order, `/api/v1/credits` to Credit,
supplier routes to Supplier, and user routes to User. See [startup](startup.md).
Set two distinct root `.env` service keys and generate the User Service JWT keys
before starting; existing account/order data lives in persistent named volumes.

For a manual walkthrough, register two accounts, create a one-credit request
from an open supplier, accept/deliver it as the second account, then confirm as
the requester. With a 20-credit initial allocation and no other activity, expect
requester `19 available / 1 reserved` after reservation, then `19 / 0` and courier
`21 / 0` after confirmation is processed. A canceled/expired one-credit request
returns its held credit to the requester. Pending states can take a worker poll
plus a frontend refresh to resolve.

These are the implemented contracts and expected results. No runtime checks,
tests, builds or containers were run during this review, per the user's request.
The repository does not include a full assignment rubric, so course-wide
compliance beyond these contracts has not been established.
