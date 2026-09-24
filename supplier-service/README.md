# Supplier Service

The current implementation provides the PostgreSQL schema, place hierarchy,
category/tag validation, and initial CSV seeding. Supplier endpoints, access
control, runtime filtering, admin workflows, and frontend integration are not
implemented yet. The FastAPI process currently initializes tables and checks
its database connection.

For installation, environment variables, database startup, seeding, and running
the service alongside User Service and the frontend, follow the
[shared startup guide](../startup.md#terminal-2-supplier-service-and-postgresql).
Paths below are relative to `supplier-service/` unless stated otherwise.

## File responsibilities

| File                    | Responsibility                                        |
| ----------------------- | ----------------------------------------------------- |
| `app/main.py`           | FastAPI startup and database availability check       |
| `app/database.py`       | Environment configuration and database connection     |
| `app/schema.py`         | Tables, constraints, and indexes                      |
| `app/places.py`         | Initial hierarchy, name normalization, seed place IDs |
| `app/classification.py` | Allowed categories and tag normalization/validation   |
| `app/seed.py`           | Validate and import the initial CSV                   |
| `tests/`                | Seed, normalization, storage, and constraint checks   |

## Schema

`app/schema.py` defines two tables. Many suppliers sit in one place, and a place
can sit inside another.

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

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID | primary key |
| `parent_id` | UUID | nullable, references `places.id` |
| `name` | text | display name, e.g. `COM2` |
| `search_key` | text | unique; normalized `name`, used for matching |
| `created_at`, `updated_at` | timestamptz | |

**`suppliers`**

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID | primary key |
| `name` | text | |
| `supplier_type` | text | one of the three categories |
| `tags` | text[] | empty by default |
| `place_id` | UUID | required, references `places.id` |
| `floor` | text | optional |
| `location_description` | text | directions within the place |
| `latitude`, `longitude` | float | per supplier, not per place |
| `opening_time`, `closing_time` | time | optional; may cross midnight |
| `image_url`, `pickup_instructions` | text | optional |
| `is_active` | bool | soft delete |
| `created_at`, `updated_at` | timestamptz | |

A place that suppliers or child places reference cannot be deleted. Supplier
`name` + `place_id` + `floor` must be unique together, including when the floor
is unknown. `place_id` and `parent_id` are indexed, and `tags` has a GIN index.

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

## Categories and tags

Every supplier has exactly one **category**, from a fixed list of three:

| Category | Covers |
| --- | --- |
| `FOOD_BEVERAGE` | food and drink |
| `RETAIL` | shops |
| `FACILITY` | printing, lockers, and other services |

Categories are deliberately broad — they drive the top-level browse filter, so
the list stays short and stable.

**Tags** describe what a supplier actually offers: `coffee`, `printing`,
`convenience`. A supplier can have any number of them, and new ones can be
added without a schema change.

Tags exist because a category alone cannot express something like coffee.
Coffee shops *are* food and beverage, so making `COFFEE` a fourth category
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
