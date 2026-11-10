# User Service

Owns accounts, roles and login. It is the only service that signs JWTs; other
services verify them with its public key. Setup is in the
[startup guide](../startup.md); the registration-credit flow is in the
[integration guide](../integration.md).

## API

Swagger: <http://localhost:8000/docs>

**Authentication.** Login returns a 15-minute RS256 access token and a 7-day
refresh token. Send the access token as `Authorization: Bearer <token>`. Each
request re-reads the account from the database, so a suspended or disabled
account is refused immediately. Access-token claims: `sub`, `email`,
`auth_role`, `active_role_mode`, `account_status`, `iat`, `exp`.

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/users/register` | anyone | Create an account (returns 201) |
| POST | `/api/v1/users/login` | anyone | Get an access token and a refresh token |
| POST | `/api/v1/users/refresh` | refresh token | Exchange a refresh token for a new pair; the old one is revoked |
| POST | `/api/v1/users/logout` | refresh token | Revoke the refresh token (returns 204) |
| GET | `/api/v1/users/{user_id}` | self, or admin | Read a profile |
| PATCH | `/api/v1/users/{user_id}` | self, or admin | Update profile fields; admins editing someone else must send `X-Admin-Reason` |
| PATCH | `/api/v1/users/{user_id}/role-mode` | self | Switch between `REQUESTER` and `COURIER`; returns the profile and a new `access_token` |
| PATCH | `/api/v1/users/{user_id}/auth-role` | admin, on another account | Set `USER` or `ADMIN`; body needs `reason` |
| PATCH | `/api/v1/users/{user_id}/status` | admin, on another account | Set `ACTIVE`, `SUSPENDED` or `DISABLED`; body needs `reason` |
| GET | `/api/v1/users` | admin | List all accounts |
| GET | `/api/v1/admin/audit-logs` | admin | Admin changes, newest first (`page`, `page_size` ≤ 100) |
| GET | `/api/v1/internal/users/{user_id}/contact` | Order Service (`X-Service-Key`) | Display name and the preferred contact only |
| GET | `/health` | anyone | Liveness |

**Request rules**

- Email must match `<nusid>@u.nus.edu`; it is stored in lower case.
- Password: at least 10 characters with an uppercase letter, a lowercase letter,
  a digit and a symbol.
- `display_name` is required, 1–100 characters.
- Profile updates accept only `display_name`, `contact_preference`,
  `telegram_handle`, `phone_number` and `profile_picture_url`. Email, role,
  status and ID cannot be changed through them.
- Admin reasons (`reason` or `X-Admin-Reason`) must be 1–500 characters.
- Refresh tokens can be used once. Suspending or disabling an account revokes
  all its refresh tokens.

## Errors

Validation errors use `{"errors": [{"field": "...", "message": "..."}]}`. Other
errors use `{"detail": "..."}`.

| Status | When |
| --- | --- |
| 401 | Missing, invalid or expired access token, or the account is no longer active ("Invalid authentication token."); wrong email or password ("Invalid email or password."); refresh token unknown, used, revoked or expired ("Your session has expired. Please log in again.") |
| 403 | Correct password but the account is suspended or disabled ("This account has been suspended." / "disabled."); reading or editing another user's profile without being admin; switching another user's role mode; an admin changing their own role or status ("An admin must change another account."); non-admin on admin routes ("Admin access is required."); wrong service key on the internal contact route |
| 404 | User not found |
| 409 | Email already registered; the change would leave no active admin ("At least one active admin must remain."); the role or status is already the requested value |
| 422 | Invalid input, including a missing or over-long admin reason |

## Data model

| Table | Columns | Notes |
| --- | --- | --- |
| `users` | `id`, `email`, `password_hash`, `display_name`, `contact_preference`, `telegram_handle`, `phone_number`, `profile_picture_url`, `auth_role`, `active_role_mode`, `account_status`, `created_at` | `email` is unique. Passwords are Argon2 hashes. |
| `refresh_tokens` | `id`, `user_id`, `token_hash`, `created_at`, `expires_at`, `revoked_at` | Only the SHA-256 hash of each token is stored; `token_hash` is unique. |
| `admin_audit_logs` | `id`, `acting_admin_user_id`, `target_user_id`, `action_type`, `previous_value`, `new_value`, `reason`, `timestamp` | Written in the same transaction as the admin change. Actions: `PROFILE_UPDATED`, `AUTH_ROLE_CHANGED`, `ACCOUNT_STATUS_CHANGED`. |
| `admin_bootstrap` | `id`, `user_id`, `timestamp` | Records the single first-admin promotion. |
| `credit_outbox` | `event_id`, `user_id`, `occurred_at`, `delivered_at`, `attempts`, `next_attempt_at` | One registration event per user (`user_id` is unique), written with the new user. |

## Background worker

`python -m app.credit_worker` (the `user-credit-worker` container) checks
`credit_outbox` every second and sends undelivered events to Credit Service
with `USER_SERVICE_KEY`. Failed sends are retried with exponential backoff
(capped at 256 seconds) and no attempt limit.

## Configuration

| Variable | Used by | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | API, worker | PostgreSQL connection |
| `JWT_PRIVATE_KEY_PATH`, `JWT_PUBLIC_KEY_PATH` | API | Signing key pair (or `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` as PEM text) |
| `CORS_ORIGINS` | API | Allowed frontend origins, comma-separated |
| `ORDER_CONTACT_SERVICE_KEY` | API | Key Order Service must send to the contact route |
| `CREDIT_SERVICE_URL`, `USER_SERVICE_KEY` | worker | Where and how to deliver registration events |

The first admin is created with `python -m app.bootstrap_admin <email>`; see the
startup guide.

## Tests

From `user-service/`:

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

Tests use a temporary SQLite database, so no PostgreSQL is needed.
