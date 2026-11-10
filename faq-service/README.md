# FAQ Service

Answers general questions about using FoC from the Markdown files in `docs/`,
through the frontend Help button, before or after login. It has its own
PostgreSQL database with pgvector and cannot read other services' data, look up
personal orders or balances, or change accounts. Setup is in the
[startup guide](../startup.md).

## How it works

```text
docs/*.md ──► one chunk per "## question" ──► BGE-small embedding (local) ──► faq_chunks (pgvector)

question ──► BGE-small embedding ──► top 5 chunks by cosine similarity, ≥ FAQ_MIN_SIMILARITY
         ──► Claude (Anthropic API) with only those chunks ──► answer citing chunk IDs
                                                         └──► no chunks / no valid citation → fixed fallback
```

- Indexing runs at startup and skips unchanged documents. HTML comments and
  `docs/README.md` are excluded.
- Embeddings run locally with `BAAI/bge-small-en-v1.5` (384 dimensions); model
  weights are downloaded during the Docker build.
- Claude must answer through a structured tool call that cites retrieved source
  IDs. Missing, invalid or uncited answers become the fixed fallback.
- Each question is independent; no chat history is sent or stored.

## API

Swagger: <http://localhost:8004/docs>. No login is needed.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/faq/chat` | Answer a question |
| GET | `/health` | Database and index readiness; `chat_ready` is false without an Anthropic key |

Request (1–1,500 characters, body at most 8 KB):

```json
{"question": "Can I cancel after a courier accepts?"}
```

Response:

```json
{
  "request_id": "...",
  "status": "answered",
  "answer": "...",
  "sources": [{"id": "...", "source_file": "requesting.md", "title": "...", "question": "...", "answer": "..."}]
}
```

`status` is `answered`, or `not_found` with the fallback answer and no sources.
Every response has an `X-Request-ID` header.

## Errors

Errors use `{"detail": "...", "request_id": "..."}` and never include provider
details or keys.

| Status | When |
| --- | --- |
| 413 | Request body over 8 KB ("Please send a shorter question.") |
| 422 | Missing question, or longer than 1,500 characters |
| 429 | More than `FAQ_REQUESTS_PER_MINUTE` requests in a minute ("FAQ support is busy…"); includes `Retry-After: 60` |
| 503 | All answer slots busy; no Anthropic key; Anthropic unavailable; database unavailable ("FAQ support is temporarily unavailable…"); index missing or out of date ("FAQ support is being updated…") |
| 504 | Anthropic did not answer in time |

## Data model

| Table | Columns | Notes |
| --- | --- | --- |
| `faq_chunks` | `id`, `source_file`, `title`, `question`, `answer`, `version`, `embedding` | One row per FAQ entry; `embedding` is a 384-dimension pgvector column. |
| `faq_index` | `id`, `version`, `embedding_profile`, `updated_at` | Content hash of the indexed docs, used to detect a stale index. |
| `faq_requests` | `request_id`, `created_at`, `outcome`, `details` | One row per request: outcome, retrieved and cited IDs, scores, timings and token usage. Question text, answers, IP addresses and account details are not stored. |

## Updating the FAQ

Edit `docs/*.md`, keeping one self-contained answer per `##` question, then
re-index without restarting:

```bash
docker compose exec faq-service python -m app.ingest
```

Answers too long for the embedding model (512 tokens) are rejected; split them.
`--force` rebuilds an unchanged index.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL with pgvector | required |
| `ANTHROPIC_API_KEY` | Enables answers | empty (answers return 503) |
| `ANTHROPIC_MODEL` | Claude model | `claude-haiku-5-5` |
| `FAQ_MIN_SIMILARITY` | Minimum cosine similarity for a chunk | `0.60` |
| `FAQ_REQUESTS_PER_MINUTE` | Shared rate limit | `30` |
| `FAQ_MAX_CONCURRENT_REQUESTS` | Answers generated at once | `2` |
| `FAQ_ANTHROPIC_TIMEOUT` | Seconds to wait for Claude | `25` |
| `FAQ_EMBEDDING_THREADS` | CPU threads for embeddings | `2` |

## Tests and evaluation

From `faq-service/`:

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
python -m app.evaluate      # retrieval check on evaluation/questions.json
python -m app.evaluate_k    # compares top-k 1, 2, 3, 4, 5 and 8
```

Tests use fake providers, so they need no model download, database or API key;
set `FAQ_TEST_DATABASE_URL` to a disposable pgvector database (name ending in
`_test`) to include the database test. The evaluation scripts need the
embedding model. Results are in [evaluation/RESULTS.md](evaluation/RESULTS.md).
