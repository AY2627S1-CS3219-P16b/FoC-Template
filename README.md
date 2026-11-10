# CS3219 — Software Design and Architecture (AY2627 Sem 1)

## Friend on Campus (FoC)

**Friend on Campus (FoC)** is a peer-to-peer campus errand platform where
students can request items to be collected from stores or facilities on
campus, and other students can fulfil (and deliver) those requests. The
platform runs on a closed credit economy — credits cannot be bought,
withdrawn, or exchanged for money, and only circulate within the platform.

---

## Team Contributions

| Team member      | Main contributions                                        | Nice-to-have (N2H) contributions |
| ---------------- | --------------------------------------------------------- | -------------------------------- |
| Chong Yi Jie     | Supplier Service; refined frontend UI; supplier seed data | RAG-based FAQ support            |
| Jessica Ange Xu  | User Service; built initial frontend                      | None                             |
| Aurora Yufei Shi | Order Service; Credit Service                             | None                             |

Shared: each member containerised their own service and implemented its
sync/async integrations.

The FAQ assistant helps users find answers about accounts, suppliers, errands,
and credits without leaving the app. It retrieves relevant passages from our
support documentation and uses them to answer questions, and shows the FAQ
answers it used. Yi Jie built this feature.

---

## Architecture

Five microservices, each with its own PostgreSQL database, plus a React frontend.
Services communicate over HTTP and never read each other's tables.

| Service            | Port | Responsibility                                                 |
| ------------------ | ---- | -------------------------------------------------------------- |
| `user-service`     | 8000 | Accounts, roles, JWT signing                                   |
| `supplier-service` | 8001 | Supplier catalogue, campus places, opening hours               |
| `credit-service`   | 8002 | Balances, reservations, credit ledger                          |
| `order-service`    | 8003 | Errands, assignments, order history, credit jobs               |
| `faq-service`      | 8004 | General FAQ support; local BGE retrieval and Anthropic answers |
| `frontend`         | 5173 | React + Vite UI; proxies `/api/v1/*` to the services           |

Two background workers deliver credit operations asynchronously through a
transactional outbox: `user-credit-worker` (initial credits on registration) and
`order-worker` (reserve, release and transfer credits; order expiry;
auto-confirming receipt).

See [service integration](integration.md) for request flows.
The Help panel is available before and after login. See [FAQ setup](faq-service/README.md)
for the Anthropic key, local embeddings, and refreshing the FAQ after edits.

---

## Quick Start (Docker)

First time: follow [startup](startup.md#first-time-setup-once-per-machine)
to generate `.env` and the JWT keys, seed suppliers and create the first admin.
Generate `.env` once only; regenerating it breaks the existing databases.

Then:

```bash
docker compose up --build -d
```

Open <http://localhost:5173>.

### API documentation

Each service README documents its endpoints, errors and data model. While the
stack is running, each service also serves interactive Swagger docs. Most
endpoints need a login token: call `POST /api/v1/users/login` in the User API
docs, then use **Authorize** with the returned `access_token`.

| Service  | Reference                                  | Swagger (while running)      |
| -------- | ------------------------------------------ | ---------------------------- |
| User     | [README](user-service/README.md#api)       | <http://localhost:8000/docs> |
| Supplier | [README](supplier-service/README.md#api)   | <http://localhost:8001/docs> |
| Credit   | [README](credit-service/README.md#api)     | <http://localhost:8002/docs> |
| Order    | [README](order-service/README.md#api)      | <http://localhost:8003/docs> |
| FAQ      | [README](faq-service/README.md#api)        | <http://localhost:8004/docs> |

Contracts between services are described in [service integration](integration.md).

---

## Repository Structure

This repository follows a **one-service-per-folder** structure: each
microservice lives in its own top-level folder with its own Dockerfile.

```text
.
├── user-service/        # FastAPI service + user-credit-worker
├── supplier-service/    # FastAPI service
├── order-service/       # FastAPI service + order-worker
├── credit-service/      # FastAPI service
├── faq-service/         # FAQ API, Markdown knowledge base, local BGE + pgvector
├── frontend/            # React + Vite
├── data/                # Supplier seed data and images
├── compose.yaml         # Full stack: 5 APIs, 2 workers, 5 databases, frontend
├── compose.dev.yaml     # Dev override: publishes database ports
├── .env.example         # Required secrets (copy to .env)
├── integration.md       # Service contracts and workflows
└── startup.md           # Setup and run guide
```

## AI Use Summary

**Tools:** OpenAI Codex, Claude Code (Claude Opus 5.5), ChatGPT

**Prohibited phases avoided:** requirements elicitation and prioritisation;
architecture and design decisions; decision rationales and trade-off analyses.
These were made and written by the team.

**Used for:**

- Reviewing teammates' pull requests, fixing syntax errors, reviewing TDD and
  implementation plans, and writing boilerplate (Codex).
- FAQ evaluation: scripts comparing retrieval depth, and measurements at different top-k values and thresholds. The team chose k = 5 and the 0.60 threshold from these results (Claude Code).
- Documentation: updating FAQ answers, README, setup guide and integration guide,
  and checking them against the code (Claude Code).
- Presentation slides: checking slide facts against the code (Claude Code).
- Implementing features the team specified, with the team reviewing and testing the code (Codex, Claude Code).

**Verification:** All AI outputs were reviewed, edited and tested by the authors.
Automated tests were run for every code change; see each log entry for details.

**Prompts and key exchanges:** see the [AI usage log](ai/usage-log.md).
