# Start Friend on Campus locally

This guide covers the User, Supplier, Credit and Order services, and React frontend.
Run commands from the repository root unless a step says otherwise.

## Run with Docker

Requires Docker Desktop running and ports 5173 and 8000–8003 free.

### First-time setup (once per machine)

Skip if `.env` and `user-service/keys/` already exist.

1. Generate `.env`. Run this once only: databases keep the password from their
   first start, so regenerating breaks them. The command will not overwrite an
   existing `.env`.

   ```bash
   [ -e .env ] && echo ".env already exists; keep it" || bash -c '
   for k in USER_SERVICE_KEY ORDER_SERVICE_KEY USER_DB_PASSWORD SUPPLIER_DB_PASSWORD CREDIT_DB_PASSWORD ORDER_DB_PASSWORD; do
     echo "$k=$(openssl rand -hex 32)"
   done' > .env
   ```

2. Generate the JWT keys:

   ```bash
   mkdir -p user-service/keys
   openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out user-service/keys/jwt-private.pem
   openssl pkey -in user-service/keys/jwt-private.pem -pubout -out user-service/keys/jwt-public.pem
   chmod 600 user-service/keys/jwt-private.pem
   ```

3. Start the stack, then seed suppliers:

   ```bash
   docker compose up --build -d
   docker compose exec supplier-service python -m app.seed
   ```

4. Register an account at <http://localhost:5173>, then make it the first admin
   and log in again:

   ```bash
   docker compose exec user-service python -m app.bootstrap_admin user-email@u.nus.edu
   ```

   This works once only. Later admins are promoted from the admin page.

### Daily use

```bash
docker compose up --build -d   # start (rebuilds changed images)
docker compose ps              # status
docker compose logs -f <service>
docker compose stop            # stop, keep data
```

`docker compose down -v` deletes all databases.

| Component    | URL                          |
| ------------ | ---------------------------- |
| Frontend     | <http://localhost:5173>      |
| User API     | <http://localhost:8000/docs> |
| Supplier API | <http://localhost:8001/docs> |
| Credit API   | <http://localhost:8002/docs> |
| Order API    | <http://localhost:8003/docs> |

### Database ports (development override)

To reach the databases from the host:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d
```

| Database      | Port |
| ------------- | ---- |
| `supplier-db` | 5433 |
| `user-db`     | 5434 |
| `credit-db`   | 5435 |
| `order-db`    | 5436 |

Use the same `-f` flags with `ps`, `stop` and `down`.

The sections below cover running the services on the host, with Docker
providing only the databases through the development override.

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

## First-time setup (running on the host)

Complete these steps once per checkout and local database. Each developer
has their own local data; Git shares source code, not database contents.

### Terminal 1: User Service

From the repository root:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d user-db
docker compose exec user-db pg_isready -U user_service -d user_db

cd user-service
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create `user-service/.env` with:

Replace `<USER_DB_PASSWORD>` with the value from the root `.env`.

```dotenv
DATABASE_URL=postgresql+psycopg://user_service:<USER_DB_PASSWORD>@localhost:5434/user_db
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
JWT_PRIVATE_KEY_PATH=keys/jwt-private.pem
JWT_PUBLIC_KEY_PATH=keys/jwt-public.pem
```

Generate the local RS256 signing key pair from `user-service/`:

```bash
mkdir -p keys
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out keys/jwt-private.pem
openssl pkey -in keys/jwt-private.pem -pubout -out keys/jwt-public.pem
chmod 600 keys/jwt-private.pem
```

The key files and environment file are ignored by Git.
Private key is available only to User Service; services that validate access tokens locally receive only `jwt-public.pem`.

Start the service in the same terminal:

```bash
python -m uvicorn app.main:create_app --factory --env-file .env --reload --port 8000
```

Leave it running. API documentation: <http://localhost:8000/docs>.

### Terminal 2: Supplier Service and PostgreSQL

In a separate terminal, from the repository root:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d supplier-db
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
DATABASE_URL=postgresql+psycopg://supplier:<SUPPLIER_DB_PASSWORD>@localhost:5433/supplier_db
JWT_PUBLIC_KEY_PATH=keys/jwt-public.pem
```

Replace `<SUPPLIER_DB_PASSWORD>` with the value from the root `.env`. The file
is git-ignored.

Copy User Service's public key so Supplier Service can verify tokens locally,
without calling User Service:

```bash
mkdir -p supplier-service/keys
cp user-service/keys/jwt-public.pem supplier-service/keys/jwt-public.pem
```

Only the public key is copied; `jwt-private.pem` stays in User Service. The
key files are ignored by Git, so this copy step is needed again on a fresh
clone.

From `supplier-service/`, import the initial supplier records:

```bash
python -m app.seed
```

For a fresh database, expect:

```text
Loaded 54 CSV rows; inserted 54; suppliers in database: 54
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
supplier read endpoints require a User Service login token. User Service is needed for login; Supplier Service verifies tokens locally. In Swagger, use Authorize with the access token
returned by login.

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

Vite forwards supplier, place, and supplier-audit requests to Supplier Service
on port 8001, credit requests to port 8002, order requests to port 8003, and other
`/api` requests to User Service on port 8000.
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
The bootstrap table's unique key resolves concurrent inserts on PostgreSQL.
Only one account is promoted; a concurrent repeat for the same account becomes
a no-op.
Subsequent promotions use the authenticated admin API.

## Stopping locally

Press Ctrl+C in each application terminal. To stop PostgreSQL while keeping
its data, run from the repository root:

```bash
docker compose stop user-db supplier-db
```

Do not use `docker compose down -v` unless you intend to delete the database
volume and its contents.
