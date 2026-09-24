# Start Friend on Campus locally

This guide covers the User Service, Supplier Service, and React frontend.
Run commands from the repository root unless a step says otherwise.

## Prerequisites

- Python 3.12 (`python3.12 --version`). Use this version for both virtual
  environments; the code does not work with Python 3.9.
- Node.js and npm.
- Docker Desktop, open and running, with `docker compose` available.

If Docker is installed on macOS but the terminal says `docker: command not
found`, open a new terminal. If needed, add its tools to the current terminal:

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
docker compose version
```

## First-time setup

Complete these steps once per checkout and local database. Each developer
has their own local data; Git shares source code and seed data, not databases.

### Terminal 1: User Service

From the repository root:

```bash
cd user-service
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create `user-service/.env` with:

```dotenv
DATABASE_URL=sqlite:///data/users.db
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
JWT_SECRET=replace-with-a-long-random-local-secret
```

Replace the secret before starting. This file is ignored by Git. All three
variables are required. The User Service currently uses SQLite.
If these variables are already exported, omit `--env-file .env`.
If your existing configuration is in `.env.dev`, use `--env-file .env.dev` instead.

Start the service in the same terminal:

```bash
python -m uvicorn app.main:create_app --factory --env-file .env --reload --port 8000
```

Leave it running. API documentation: <http://localhost:8000/docs>.

### Terminal 2: Supplier Service and PostgreSQL

In a separate terminal, from the repository root:

```bash
docker compose up -d supplier-db
docker compose exec supplier-db pg_isready -U supplier -d supplier_db
```

Wait for `accepting connections` before proceeding. If PostgreSQL is still
starting, run the readiness command again after a few seconds.

```bash
cd supplier-service
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create `supplier-service/.env.dev` with:

```dotenv
DATABASE_URL=postgresql+psycopg://supplier:supplier_local_dev@localhost:5433/supplier_db
```

These local development credentials match `compose.yaml`. The environment
file is ignored by Git. FastAPI runs on your Mac and connects to port 5433;
Docker forwards that connection to PostgreSQL on port 5432 inside the container.

From `supplier-service/`, import the initial supplier records:

```bash
python -m app.seed
```

For a fresh database, expect:

```text
Loaded 21 CSV rows; inserted 21; suppliers in database: 21
```

Run the import for a fresh database; it is not needed on every startup.
It creates the tables if missing, seeds the authored place catalogue, and
imports suppliers linked to those places. Existing records are skipped.

Start the service in the same terminal:

```bash
python -m uvicorn app.main:create_app --factory --reload --port 8001
```

Wait for `Application startup complete` and leave it running. Startup checks
the PostgreSQL connection. API documentation: <http://localhost:8001/docs>;
no supplier endpoints have been added yet.

See the [Supplier Service README](supplier-service/README.md) for schema and
design decisions, seed-data conventions, database maintenance, and tests.

### Terminal 3: Frontend

In a separate terminal, from the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Register at
<http://localhost:5173/?screen=register>, then log in at
<http://localhost:5173/?screen=login>.

Vite currently forwards `/api` requests to User Service on port 8000. Supplier
screens still use mock data; supplier API integration is not implemented yet.
For a remotely hosted User Service, set `VITE_USER_API_URL` to its origin before
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

## Stopping locally

Press Ctrl+C in each application terminal. To stop PostgreSQL while keeping
its data, run from the repository root:

```bash
docker compose stop supplier-db
```

Do not use `docker compose down -v` unless you intend to delete the database
volume and its contents.
