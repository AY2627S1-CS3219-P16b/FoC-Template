# Supplier Service

The current implementation provides the PostgreSQL schema, place hierarchy,
category/tag validation, initial CSV seeding, read endpoints for browsing,
searching, filtering, sorting, and paginating suppliers, and admin endpoints for
creating, editing, and hiding them. The frontend supplier listing and admin
screen consume them. Reading requires an active authenticated user; changing
records requires an admin.

For installation, environment variables, database startup, seeding, and running
the service alongside User Service and the frontend, follow the
[shared startup guide](../startup.md#terminal-2-supplier-service-and-postgresql).
Paths below are relative to `supplier-service/` unless stated otherwise.

## File responsibilities

| File                      | Responsibility                                           |
| ------------------------- | -------------------------------------------------------- |
| `app/main.py`             | FastAPI startup and HTTP endpoints                       |
| `app/api_schemas.py`      | Request and response models                              |
| `app/supplier_queries.py` | Browse, search, filter, sort, and place lookups          |
| `app/admin_queries.py`    | Admin writes, each recorded in the audit log             |
| `app/database.py`         | Environment configuration and database connection        |
| `app/schema.py`           | Tables, constraints, and indexes                         |
| `app/places.py`           | Initial hierarchy, name normalization, seed place IDs    |
| `app/auth.py`             | Verify callers through User Service                      |
| `app/classification.py`   | Allowed categories and tag normalization/validation      |
| `app/seed.py`             | Validate and import the initial CSV                      |
| `tests/`                  | Seed, storage, authentication, and admin-endpoint checks |

## API

Interactive docs run at <http://localhost:8001/docs>. Click **Authorize** and
paste the access token returned by User Service login (without the Bearer prefix).

### Authentication

Every endpoint requires `Authorization: Bearer <access_token>`, obtained from
User Service login. Tokens are verified through User Service on each request, so
it must be running and `USER_SERVICE_URL` must point at it (default
`http://127.0.0.1:8000`; in containers use the service's network address, not
localhost). Supplier Service holds no JWT secret of its own.

Verifying on every request means a suspended account loses access immediately
rather than when its token expires.

| Status | Meaning                                                   |
| ------ | --------------------------------------------------------- |
| `401`  | Missing, invalid or expired token, or an inactive account |
| `503`  | User Service unreachable within three seconds             |

Any logged-in user can read. Changing records requires `auth_role` of `ADMIN`,
which returns `403` when the caller is known but not an admin.

| Endpoint                        | Purpose                                           | Who      |
| ------------------------------- | ------------------------------------------------- | -------- |
| `GET /api/v1/places`            | Every place with its parent, for filter dropdowns | any user |
| `GET /api/v1/suppliers`         | Browse, search, filter, sort, paginate            | any user |
| `GET /api/v1/suppliers/{id}`    | One supplier for Order Service                    | any user |
| `POST /api/v1/suppliers`        | Add a supplier                                    | admin    |
| `PATCH /api/v1/suppliers/{id}`  | Change the supplied fields                        | admin    |
| `DELETE /api/v1/suppliers/{id}` | Hide a supplier from browsing                     | admin    |
| `POST /api/v1/places`           | Add a place, optionally inside another            | admin    |
| `GET /api/v1/supplier-changes`  | Every recorded change, newest first               | admin    |

### Admin writes

`PATCH` and `DELETE` require an `X-Admin-Reason` header of 1 to 500 characters;
`POST` does not, because a created record is its own explanation. This matches
User Service, where registering an account needs no reason but changing or
suspending one does.

Every write is recorded in `supplier_audit_logs` in the same transaction as the
change, so a change cannot exist without its audit entry.

`DELETE` is a soft delete: it sets `is_active` to false so the supplier leaves
browsing while orders that reference it still resolve. `PATCH` with
`is_active: true` restores it. Admins can pass `include_inactive=true` when
browsing to find hidden suppliers; it returns `403` for everyone else.

A place name must be unique, and so must a supplier name at the same place.
Places cannot be deleted while suppliers or child places reference them.

| Status | Meaning                                                  |
| ------ | -------------------------------------------------------- |
| `403`  | Signed in, but not an admin                              |
| `404`  | Unknown supplier, place, or parent place                 |
| `409`  | Duplicate name, or the change is already applied         |
| `422`  | Invalid field, or a missing `X-Admin-Reason` on a change |

### Search and filter options

These optional URL parameters control `GET /api/v1/suppliers`:

| Parameter           | Purpose                                                               | Example               |
| ------------------- | --------------------------------------------------------------------- | --------------------- |
| `q`                 | Search part of a supplier name, location, or tag                      | `q=coffee`            |
| `type`              | Category: `FOOD_BEVERAGE`, `RETAIL`, or `FACILITY`                    | `type=RETAIL`         |
| `place`             | Location UUID or search key; includes child places                    | `place=lt27`          |
| `sort`              | `name` (default), `place`, or `category`; `-` reverses                | `sort=-name`          |
| `page`, `page_size` | Page number and results per page; defaults 1 and 20, maximum size 100 | `page=2&page_size=10` |

The response contains `items` (the suppliers on this page), `page`, `page_size`,
`total` (matching suppliers), and `total_pages`.

| Status | Meaning                                                     |
| ------ | ------------------------------------------------------------ |
| `200`  | Includes a search matching nothing: empty `items`, `total` 0 |
| `404`  | Unknown place or supplier                                    |
| `422`  | Invalid parameter value                                      |

Browsing shows active suppliers only. `GET /api/v1/suppliers/{id}` does not:
any authenticated user who has an id, not only an admin, can look up a hidden
supplier's full record. This is intentional so an order placed before a
supplier was hidden still resolves; Order Service is the intended caller, and
no screen calls this endpoint yet. Both endpoints return the same fields.

## Schema

`app/schema.py` defines three tables. Many suppliers sit in one place, a place
can sit inside another, and every admin write is recorded in an audit table.

```
        ┌──────────────────────────┐
        │  places                  │
   ┌───▶│    id                    │   parent_id lets a place
   │    │    parent_id ────────────┼─┐ nest inside another:
   │    │    name                  │ │ The Terrace → COM3
   │    │    search_key            │ │ Frontier    → LT27
   │    └──────────────────────────┘ │
   │                 ▲               │
   └─────────────────┼───────────────┘
                     │ place_id   (many suppliers → one place)
        ┌────────────┴─────────────┐
        │  suppliers               │
        │    id, name, ...         │
        └──────────────────────────┘
```

**`places`**

| Column                     | Type        | Notes                                        |
| -------------------------- | ----------- | -------------------------------------------- |
| `id`                       | UUID        | primary key                                  |
| `parent_id`                | UUID        | nullable, references `places.id`             |
| `name`                     | text        | display name, e.g. `COM2`                    |
| `search_key`               | text        | unique; normalized `name`, used for matching |
| `created_at`, `updated_at` | timestamptz |                                              |

`id` is the primary key. `parent_id` nests a place inside another — Frontier's
`parent_id` points at LT27 — so a supplier's location can be a whole building
or a specific venue inside one. A place that suppliers or child places
reference cannot be deleted.

**`suppliers`**

| Column                             | Type        | Notes                                                   |
| ---------------------------------- | ----------- | ------------------------------------------------------- |
| `id`                               | UUID        | primary key                                             |
| `name`                             | text        |                                                         |
| `supplier_type`                    | text        | one of the three categories                             |
| `tags`                             | text[]      | empty by default                                        |
| `place_id`                         | UUID        | required, references `places.id`                        |
| `floor`                            | text        | optional; letters and digits only, e.g. `B1`, `G`, `13` |
| `location_description`             | text        | directions within the place                             |
| `latitude`, `longitude`            | float       | per supplier, not per place                             |
| `opening_time`, `closing_time`     | time        | required; see Opening hours                             |
| `image_url`, `pickup_instructions` | text        | optional                                                |
| `is_active`                        | bool        | soft delete                                             |
| `created_at`, `updated_at`         | timestamptz |                                                         |

Two suppliers cannot share a name at the same place and floor. The comparison
ignores capitals, spaces and punctuation, so `Makan Malah`, `makan  malah` and
`MAKAN-MALAH` collide, and an unknown floor counts as a value rather than
matching any floor. The key is computed by a unique index rather than stored in
a column, because nothing reads it — unlike `places.search_key`, which is
queried when resolving `?place=com2`.

It compares spellings, not meanings: `Makan Malah @ NUS` is still a separate
record, and `Starbucks` at two different places is two valid suppliers. Deciding
that a differently worded name is the same shop is an admin judgement, not
something a constraint can make.

**`supplier_audit_logs`**

| Column                 | Type        | Notes                                                                           |
| ---------------------- | ----------- | ------------------------------------------------------------------------------- |
| `id`                   | UUID        | primary key                                                                     |
| `acting_admin_user_id` | UUID        | a User Service id; no foreign key                                               |
| `entity_type`          | text        | `SUPPLIER` or `PLACE`                                                           |
| `entity_id`            | UUID        | the changed row's id; no foreign key                                            |
| `action_type`          | text        | `SUPPLIER_CREATED`, `SUPPLIER_UPDATED`, `SUPPLIER_DEACTIVATED`, `PLACE_CREATED` |
| `previous_value`       | JSONB       | changed fields before the write; `{}` on a create                               |
| `new_value`            | JSONB       | changed fields after the write                                                  |
| `reason`               | text        | required for a change; null for a create                                        |
| `created_at`           | timestamptz |                                                                                 |

Written in the same transaction as the change it records, so a write cannot
exist without its audit entry. User Service keeps its own separate audit log
for account changes; this table only records changes to suppliers and places.

## Places

A place is anywhere on campus a supplier can sit: a building, an area, or a
venue inside one.

- **`name`** is the display name, e.g. `COM2` or `Prince George's Park`. It is
  the one spelling used everywhere, so the same building is never split across
  variants like `Com 2` and `Com2`.
- **`parent_id`** nests a place inside another. Frontier is inside LT27; The
  Terrace is inside COM3. A supplier points at its most specific place, and
  filtering by a parent also returns suppliers in its children — so a user can
  filter by either the building or the canteen.
- **`search_key`** is `name` with case, spaces, and punctuation removed
  (`COM 2` → `com2`). Incoming text is matched against it, so a typed variant
  resolves to the existing place rather than creating a near-duplicate.

## Opening hours

Both times are required, so a caller never has to treat unknown hours as a
special case: Order Service can refuse an order placed while a supplier is
shut.

- **Open around the clock** is stored as `00:00` to `23:59`. Five suppliers use
  this, including the COM2 printer.
- **Trading past midnight** is stored with a closing time _earlier_ than the
  opening time, as Supersnacks does with `11:00` to `02:00`.

The second point matters for querying. "Is it open now?" is not a plain range
comparison: when `closing_time < opening_time` the window wraps, so the test is
`now >= opening OR now <= closing` rather than `opening <= now <= closing`.

## Categories and tags

Every supplier has exactly one **category**, from a fixed list of three:

| Category        | Covers                                |
| --------------- | ------------------------------------- |
| `FOOD_BEVERAGE` | food and drink                        |
| `RETAIL`        | shops                                 |
| `FACILITY`      | printing, lockers, and other services |

Categories are deliberately broad — they drive the top-level browse filter, so
the list stays short and stable.

**Tags** describe what a supplier actually offers: `coffee`, `printing`,
`convenience`. A supplier can have any number of them, and new ones can be
added without a schema change.

Tags exist because a category alone cannot express something like coffee.
Coffee shops _are_ food and beverage, so making `COFFEE` a fourth category
would drop them out of a food search. As a tag, both work: `FOOD_BEVERAGE`
returns all 16 food suppliers, `coffee` narrows to the 5 that serve it.

In the CSV, `Type` holds the category and `Tags` is a semicolon-separated list
(`coffee;halal`); blank means none. Tags are stored lowercase, so `Coffee` and
`COFFEE` are the same tag.

## Seed data

> **Note:** `data/csv/supplier-seed-data.csv` has been edited from the version
> supplied in the template repository. Do not overwrite it with the original.

Changes from the supplied file:

- `Type` now holds category codes (`FOOD_BEVERAGE`, `RETAIL`, `FACILITY`)
  instead of the original labels such as `Food/Coffee`.
- A `Tags` column was added, carrying `coffee`, `printing`, and `convenience`.
- Building names were standardized to their canonical spelling, so the same
  building no longer appears as both `Com 2` and `Com2`.
- Image URLs point at `raw.githubusercontent.com` rather than the `github.com`
  `/blob/` links supplied, which return an HTML page rather than an image.
- The file is saved as UTF-8.

The importer validates every row and fails with the row number rather than
importing partial data.

## Database maintenance

PostgreSQL data persists in the Docker volume `supplier-db-data` across service
and container restarts. `create_all()` creates missing tables only; changes to
an existing table's structure require a database migration.

To reset local seed data, stop Supplier Service and recreate its database from
the repository root:

```bash
docker compose exec supplier-db dropdb -U supplier --maintenance-db=postgres --force supplier_db
docker compose exec supplier-db createdb -U supplier supplier_db
```

This deletes local supplier edits. Then run `python -m app.seed` from
`supplier-service/` and restart the service.

To inspect records from the repository root:

```bash
docker compose exec supplier-db psql -U supplier -d supplier_db -c 'SELECT s.name, s.supplier_type, p.name AS place, s.is_active FROM suppliers s JOIN places p ON p.id = s.place_id ORDER BY s.name;'
```

## Tests

From `supplier-service/`, run:

```bash
python -m unittest discover -s tests -v
RUN_POSTGRES_TESTS=1 python -m unittest discover -s tests -v
```

The first command runs checks without database access. The second also tests
imports, stored relationships, duplicate prevention, and foreign-key
constraints in a temporary PostgreSQL schema, then removes that test schema.
