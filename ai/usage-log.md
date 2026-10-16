# AI usage log

## 2026-10-16 — Order Service schema

- Tool: OpenAI Codex.
- Mode: Generated implementation and schema definitions.
- Affected file: `order-service/app/schema.py`.
- Human review: Pending. Database integration and behavior tests are also pending.
- Course-policy note: Appendix 2 reserves schema/design decisions for the team.
  This exchange included AI-generated schema decisions and must not be described
  as implementation-only assistance.

### Exact prompt

```text
Help me fill out the order service schema.py first with tables, fields, and constraints

thinking of having:
order_log (all operations)
orders (id, requester, courier, supplier, pickup, item, delivery, credit, status, expires at, created at, updated at, idempotencykey)

and other tables u think we need. make sure schema matches style of other services
```

### Key output and verification

Generated SQLAlchemy Core definitions for `orders`, `order_log`, and `credit_jobs`.
The schema includes pending credit states, supplier pickup snapshots, a creation
request fingerprint, requester-scoped idempotency, local foreign keys, checks,
and query indexes. See the affected file for the full generated code.

Imported the schema and compiled all table and index definitions using the
PostgreSQL dialect with the existing `/private/tmp/foc-d3-venv` runtime.
`git diff --check` passed. No live database checks were performed.

### Follow-up — remove request fingerprint

Exact prompt: `remove` (referring to `request_fingerprint` and its constraint).

Removed the column, its comment, and its length constraint from the schema.
Requester-scoped idempotency remains. Comparing retry contents against the
stored order remains implementation work in the query layer.

### Follow-up — inline constraints

Exact prompt: `place all constraints inside the table`

Moved all appended checks into their respective `Table(...)` declarations.
Compared the compiled check expressions before and after the refactor (ignoring
table-name qualification); every check is preserved. PostgreSQL table and index
definitions compile, and `git diff --check` passes.

### Follow-up — index comments

Exact prompt: `add a comment explaining the indexes`

Added comments describing requester/courier listings, expiry queries, order
history ordering, and the partial index for unfinished credit jobs.

### Follow-up — Order Service authentication

Exact prompt: `Fill out order schemas auth.py, reusing as much logic from other auth.py as possible`

Adapted Supplier Service's `CurrentUser`, public-key loading, RS256 JWT
verification, unauthorized response, and admin guard into
`order-service/app/auth.py`. Removed supplier-specific admin-reason handling.
Role mode passes through; order ownership and assignment checks remain the
responsibility of order operations. Verification uses token claims, so later
account changes are not observed until a new token is issued or the old one expires.

Added `order-service/tests/test_auth.py`. All eight authentication tests passed
using `PYTHONPATH=order-service /private/tmp/foc-d3-venv/bin/python -m unittest
discover -s order-service/tests -p test_auth.py -v`. Tests cover accepted roles,
admin access, rejected credentials/claims/signatures/algorithms, expiry, and key
configuration. Human review remains pending.
