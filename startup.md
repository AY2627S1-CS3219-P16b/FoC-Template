# Start Friend on Campus locally

Run the user service and frontend in separate terminals from the repository
root.

## Terminal 1: user service

```bash
cd user-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:create_app --factory --env-file .env --reload --port 8000
```

For local development, you can create `user-service/.env` with these variables set:

```dotenv
DATABASE_URL=sqlite:///data/users.db
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
JWT_SECRET=replace-with-a-long-random-local-secret
```

Replace the secret before starting. The `.env` file is ignored by Git. All
three variables are required; the service fails at startup when any is missing.
If the variables are already exported, omit `--env-file .env` from the command.

The API is at `http://localhost:8000`; interactive documentation is at
`http://localhost:8000/docs`.

## Terminal 2: frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite forwards `/api` requests to the user
service on port 8000. Unauthenticated visitors see the landing page; direct
registration and login routes are `?screen=register` and `?screen=login`.

For a remotely hosted API, set `VITE_USER_API_URL` to its origin before
starting or building the frontend.

## Admin Setup

Complete the user service setup from above and register the first administrator as a
normal user. Then provide the same `DATABASE_URL` used by the service and
run this command from `user-service/`:

```sh
.venv/bin/python -m app.bootstrap_admin user-email@u.nus.edu
```

If configuration is supplied in a file, pass its path with `--env-file PATH`.
An existing `DATABASE_URL` environment variable takes precedence over that
file. The `.venv/bin/python` path ensures the command uses the interpreter
with the service dependencies.

The first successful run promotes the existing active account associated with
`user-email@u.nus.edu` to admin. A deployment job may safely repeat the same
command.

Only an operator with database connection credentials can run this command.
Repeating it for the same account succeeds without changing the account.
It never resets a password, restores a demoted role, or reactivates a disabled
account. Running it for a different account after initialization is rejected.
SQLite takes a write lock before checking bootstrap state. The bootstrap
table's unique key resolves concurrent inserts on PostgreSQL. Only one account
is promoted; a concurrent repeat for the same account becomes a no-op.
Subsequent promotions use the authenticated admin API.
