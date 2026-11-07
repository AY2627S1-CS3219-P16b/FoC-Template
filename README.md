# CS3219 — Software Design and Architecture (AY2627 Sem 1)

## Friend on Campus (FoC)

**Friend on Campus (FoC)** is a peer-to-peer campus errand platform where
students can request items to be collected from stores or facilities on
campus, and other students can fulfil (and deliver) those requests. The
platform runs on a closed credit economy — credits cannot be bought,
withdrawn, or exchanged for money, and only circulate within the platform.

---

## Team Contributions

| Team member | Main contributions | Nice-to-have (N2H) contributions |
| --- | --- | --- |
| Aurora Yufei Shi | Built the Credit Service and Order Service. | None. |
| Jessica Ange Xu | Built the User Service and the frontend base. | None. |
| Chong Yi Jie | Built the Supplier Service, polished the frontend and prepared the supplier seed data. | RAG-based FAQ and support (N2). |

The FAQ assistant helps users find answers about accounts, suppliers, errands,
and credits without leaving the app. It retrieves relevant passages from our
support documentation and uses them to answer questions, with links to the
sources. Yi Jie built this feature.

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
`order-worker` (reserve, release and transfer credits; order expiry).

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

We used AI tools, including OpenAI Codex, to help review teammates' pull requests,
fix syntax errors, review TDD and implementation plans, and write boilerplate
code. Codex also helped review the implementation against the project brief and
edit this README.

The team remains responsible for checking the suggestions and understanding the
submitted code. Recorded prompts, key responses, and verification notes are in
our [AI usage log](ai/usage-log.md). 
