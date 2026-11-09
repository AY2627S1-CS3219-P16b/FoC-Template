# AI usage log

## 2026-11-09 — FAQ threshold measured at 0.65, 0.60 and 0.55; changed to 0.60

- Tool: Claude Code (Claude Opus 5.5).
- Mode: measurement and implementation of a team decision.
- Prompts: "having 70/85 retrieval rate is too low, consider lowering the FAQ threshold to 0.60 or 0.55.
- Decision (Chong Yi Jie): Chong Yi Jie raised the 70/85 recall as a concern,
  asked for options, and chose to lower the threshold to 0.60 out of the options
  presented (keep 0.65, or lower to 0.60).
- AI role: ran `app.evaluate_k` at thresholds 0.65, 0.60 and 0.55 and reported
  the measured effect (more vague questions retrieved, more unrelated questions
  reaching Claude); then applied the chosen value.
- Changes: default `FAQ_MIN_SIMILARITY` set to 0.60 in `.env.example`,
  `compose.yaml`, `faq-service/app/config.py` and `faq-service/README.md`;
  `faq-service/evaluation/RESULTS.md` updated with the new table, a threshold
  comparison and a live check.
- Verification: `app.evaluate_k` and `app.evaluate` (77/85 at k = 5, 11/15
  unrelated rejected by threshold); FAQ unit tests (26 passed, 1 skipped); live
  service check: all 15 unrelated questions returned the fallback with no
  sources, and the 7 newly retrieved supported questions were answered with
  citations.
- Human review: Chong Yi Jie reviewed the threshold comparison and live-check results, chose 0.60, and checked the updated RESULTS.md.

## 2026-11-09 — FAQ account answers and evaluation rerun

- Tool: Claude Code (Claude Opus 5.5).
- Prompts: "check if FAQ md files have anything else pending for review, remove them if its already resolved.".
- Changes: rewrote the account-status, suspended-by-mistake and delete-account
  answers in `faq-service/docs/account.md` to match the new suspended-login
  message (commit `da21dfa`) and to state that there is no in-app admin contact;
  removed their REVIEW comments. Reran the evaluation and updated the numbers in
  `faq-service/evaluation/RESULTS.md` (recall at k = 5 unchanged at 70/85).
- Verification: checked wording against `user-service/app/main.py`,
  `api_schemas.py` and `frontend/src/api/session.js`; ran `app.evaluate`,
  `app.evaluate_k` and the FAQ unit tests (26 passed, 1 skipped) in the FAQ image.
- Human review: Chong Yi Jie read the updated FAQ answers in account.md and checked them against the app’s login and account behaviour.

## 2026-11-08 — FAQ updates for give-back and credit retry limit

- Tool: Claude Code (Claude Opus 5.5).
- Prompts: "check if we handled all the questions that would potentially be asked by the users, suggest if there are still gaps?";
- Changes: updated FAQ answers in `faq-service/docs/requesting.md` and
  `account.md` to match commit `28aeb33` (credit processing stops after repeated
  failures and needs an admin retry; a given-back errand returns to Open and can
  be cancelled; admins can retry credit processing); fixed a sentence in
  `couriers.md`. Updated the retrieval table in `faq-service/evaluation/RESULTS.md`
  with the rerun and reworded its end-to-end evaluation section.
- Verification: checked the wording against `order-service/app/worker.py`,
  `order_queries.py` and the frontend; reran `app.evaluate_k`, `app.evaluate` and
  the FAQ unit tests (26 passed, 1 skipped); six live questions answered correctly.
- Top-k decision (Chong Yi Jie): chose k = 5 from the evaluation table, with
  this reasoning in their own words: "out of 85 questions tested the retrieval
  accuracy increases, however after 5 it remains stagnant, hence we decided
  with k = 5". Limitation noted by Chong Yi Jie: "we only evaluated 100 questions but
  for total 65 questions in faq docs and this small service". The AI only
  checked this reasoning against the results.
- AI role for top-k: on request ("yes i think we will use k=5"), changed
  retrieval to 5 in `faq-service/app/database.py`, `support.py` and
  `evaluate.py`, and updated the FAQ README and `RESULTS.md`. Unit tests pass and
  `app.evaluate` reports 70/85 recall at k = 5 (threshold 0.65 at the time).
- Human review: Chong Yi Jie read the updated FAQ answers, checked them against Aurora’s changes, and confirmed the k = 5 results in RESULTS.md.

## 2026-11-07 — FAQ retrieval evaluation and prompt fix

- Tool: Claude Code (Claude Opus 5.5).
- Mode: generating evaluation scripts and test data; measurement; prompt fix.
- Prompts: "evaluate different top-k retrievals to see best result"; "add more test set instead, try vague questions".
- Decisions (Chong Yi Jie): to evaluate retrieval depth before choosing k; to
  enlarge the test set to 100 questions; to include vague and unrelated
  questions rather than only ones that pass; that answers must not refer to
  "our FAQ".
- Changes: added `faq-service/app/evaluate_k.py` (compares top-k 1, 2, 3, 4, 5, 8
  with clear/vague breakdown); expanded `faq-service/evaluation/questions.json` from
  21 to 100 questions (85 supported covering all 65 FAQ entries, 14 of them vague;
  15 unrelated); recorded results in `faq-service/evaluation/RESULTS.md`. Tightened
  the Claude system prompt in `faq-service/app/support.py` so unrelated questions
  cite nothing (fixed fallback) and answers do not refer to "the information I have".
- Verification: ran both evaluation scripts in the FAQ Docker image; sent 20 live
  questions to the running service before and after the prompt change (0/20
  answers mention the FAQ or its sources afterwards); FAQ unit tests pass (26
  passed, 1 skipped). Test questions were written by the AI tool.
- Human review: Chong Yi Jie reviewed the test questions and the evaluation results, and checked several live answers after the prompt change.

## 2026-10-17 — Order Service review and four-service integration

- Tool: OpenAI Codex.
- Prompts: "scan thru order service and ensure everything works and fits the requirements completely. you can simplify code and make things more concise in places if neeeded"; "remove all the tests u added"; "Ensure that all 4 services are integrated with teach other. specifically credit and order services."
- Changes: completed the pending credit-job query and independent credit/expiry
  worker; implemented reservation reconciliation, stable operation keys and
  delayed-reservation expiry; simplified pagination, supplier validation and HTTP
  error handling; wired the worker into Compose. Replaced frontend mock order
  actions/direct reservation mutations with Order Service calls and polling.
  Role switching now issues a fresh User Service JWT and the frontend stores it.
- Documentation: added the Order Service README and root integration guide;
  updated startup and credit integration notes.
- Verification: source/configuration review only. No tests, builds, dependency
  installation or containers were run. Test files added in this conversation
  were removed as requested; pre-existing authentication tests were retained.
- Human review: pending. Full assignment rubric is not present in the repository;
  course-wide compliance and runtime behavior have not been independently verified.

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
