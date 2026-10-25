# FAQ support

General support from the six Markdown files in `docs/`, available through the
frontend Help button before and after login. The API runs on port 8004 and owns
a separate PostgreSQL database with pgvector. It cannot read the other services'
databases, look up personal orders or balances, or change account data.
Future personal lookups are tracked in [TODO.md](TODO.md).

## How it works

1. At container startup, the indexer removes HTML comments, excludes `docs/README.md`,
   and creates one chunk per non-empty `##` question and answer.
2. Local `BAAI/bge-small-en-v1.5` embeddings are generated through FastEmbed's CPU
   ONNX runtime. Model weights are downloaded during the Docker build, not during
   requests. A changed index is replaced in one database transaction.
3. Questions are embedded locally. pgvector retrieves the four closest FAQ chunks
   by cosine similarity; results below `FAQ_MIN_SIMILARITY` are dropped.
4. Claude, called directly through Anthropic's API, receives the question and
   retrieved evidence. Its structured answer must cite retrieved source IDs.
   Unsupported, malformed, truncated or uncited results become a fixed fallback.
   The frontend displays the source questions and their full indexed answers.

Questions are independent. The browser keeps only an in-memory conversation
display; previous messages are not sent as context or saved as chat history.
Closing and reopening Help preserves the display; Clear conversation or a page
reload removes it.

## Configuration and startup

For an existing installation, add these entries to the root `.env` without
regenerating its existing secrets:

```dotenv
FAQ_DB_PASSWORD=<a-new-unique-database-password>
ANTHROPIC_API_KEY=<your-Anthropic-API-key>
ANTHROPIC_MODEL=claude-haiku-5-5
FAQ_MIN_SIMILARITY=0.65
FAQ_REQUESTS_PER_MINUTE=30
```

Use a URL-safe database password, such as a value from `openssl rand -hex 32`.
Choose a Claude model available to your Anthropic account; `ANTHROPIC_MODEL` is
independent of embeddings. Keys stay in backend configuration and are never
sent to the browser. No AWS account or embedding API key is needed. Anthropic
answer generation is still billed by Anthropic.

From the repository root:

```bash
docker compose up --build -d faq-service frontend
docker compose logs -f faq-service
```

The first build downloads dependencies and model weights. Initial indexing runs
before the API starts. Unchanged startups skip document embedding. `/health`
reports database/index readiness and whether an Anthropic key is configured;
it does not spend money validating that key with Anthropic. An empty key lets
the service start, but relevant questions return 503 until configured.
FAQ availability is independent of the core application's health.

## Editing the FAQ later

Edit the Markdown files and keep each answer self-contained. The docs are mounted
read-only into the container; refresh the index without rebuilding or restarting:

```bash
docker compose exec faq-service python -m app.ingest
```

Only public content changes trigger re-embedding. HTML-comment-only edits do not.
Chunks that reach BGE's 512-token limit are rejected instead of silently truncated;
split long answers into shorter self-contained questions.
A content hash detects stale or missing indexes, and the API returns 503 until
they are refreshed. Indexing makes no Claude API calls. `--force` rebuilds an
unchanged index too.

Review comments never reach the assistant, but stripping a comment does not
establish that its associated answer is correct. Keep public answers aligned
with current product behaviour while pending decisions are resolved.
The similarity threshold is an initial retrieval setting, not a calibrated
probability of correctness. Checking source IDs cannot prove every generated
claim is grounded; review answers from the real Claude model too.

## API

Public `POST /api/v1/faq/chat`, with no login token:

```json
{"question": "Can I cancel after a courier accepts?"}
```

The response includes `request_id`, `status` (`answered` or `not_found`), `answer`,
and `sources` (`id`, `source_file`, `title`, `question`, `answer`). API docs:
<http://localhost:8004/docs>. The frontend uses Vite's `/api/v1/faq` proxy.

Questions must contain 1–1,500 characters. At most two pipelines run concurrently;
all callers share a 30-request/minute instance budget by default. Multiple API
replicas would need a shared limiter. Responses use 422 for invalid input, 429
for rate limits, 503 for an unavailable/busy service, and 504 for provider timeout.
Errors show a request reference instead of provider details or credentials.

## Logging

Structured `faq_request` events go to stdout and the FAQ-owned `faq_requests`
table. They include request ID, outcome, knowledge version, retrieved/cited IDs,
similarity scores, timings and reported token usage. Question text, answers,
IP addresses, account identifiers and credentials are not stored in these logs.
Anthropic receives the current question and selected FAQ excerpts for generation;
its account data policies apply separately.

```bash
docker compose logs --tail=100 faq-service
docker compose exec faq-db psql -U faq_service -d faq_db -c \
  "SELECT outcome, count(*) FROM faq_requests GROUP BY outcome;"
```

Docker stdout logs rotate at 10 MB across three files. Database metadata persists
in `faq-db-data`; there is no automatic retention job yet. Operators can remove
old metadata according to their chosen retention policy.

## Running on the host

Use Python 3.12. Expose PostgreSQL with the development override:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d faq-db
cd faq-service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Create `faq-service/.env` with `DATABASE_URL` pointing to
`postgresql+psycopg://faq_service:<FAQ_DB_PASSWORD>@localhost:5437/faq_db`, your
`ANTHROPIC_API_KEY`, and optionally `ANTHROPIC_MODEL`. Then:

```bash
python -m dotenv run -- python -m app.ingest
python -m uvicorn app.main:create_app --factory --env-file .env --port 8004
```

Host execution downloads the model once into `FAQ_MODEL_CACHE` (default
`/tmp/foc-faq-models`). Set `FAQ_MODEL_LOCAL_ONLY=true` once cached to require
offline loading. `FAQ_EMBEDDING_THREADS` defaults to two CPU threads.

## Verification

From `faq-service/`, after installing development dependencies:

```bash
python -m pytest tests -q
python -m app.evaluate
```

Unit/API tests inject providers and need no downloads, database or paid calls.
Set `FAQ_TEST_DATABASE_URL` to a disposable pgvector database whose name ends in
`_test` to also run the real database integration check.

`app.evaluate` runs the real local model on curated questions under `evaluation/`.
It checks expected FAQs in the top four, reports unrelated queries rejected by
the threshold, and measures warm embedding plus in-memory search latency. It
does not measure PostgreSQL or Claude latency. This is a small smoke set, not a
broad quality benchmark.

Initial local smoke run (2026-10-25): 59 chunks, expected evidence retrieved for
13/13 supported questions, and 3/3 clearly unrelated questions rejected by the
threshold. Warm embedding plus in-memory search measured 6.83 ms median and
9.93 ms p95 on the development machine. These timings exclude PostgreSQL and
Claude and will vary across machines.
The final Docker image also passed the same 13/13 and 3/3 checks with
`--network none`; warm embedding plus in-memory search measured 18.21 ms median
and 26.82 ms p95 inside that container.

## References

- [BGE model card](https://huggingface.co/BAAI/bge-small-en-v1.5)
- [FastEmbed](https://qdrant.github.io/fastembed/Getting%20Started/)
- [pgvector](https://github.com/pgvector/pgvector)
- [Anthropic Python SDK](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python)
