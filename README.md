# Friend on Campus (FoC)

**A campus errand platform for NUS students.** Request a pickup from a campus supplier, deliver an errand for another student, and earn credits.

CS3219 Software Design and Architecture · AY2026/27 Semester 1 · Group 16

[Getting started](#getting-started) · [Architecture](#architecture) · [API documentation](#api-documentation) · [Team contributions](#team-contributions)

> **Local deployment:** run the app with Docker Compose and open <http://localhost:5173>. FAQ answers additionally require an Anthropic API key; the core application runs without one.

## Features

| Area           | What you can do                                                                                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Accounts       | Register with an NUS student email, manage a profile, and switch between requester and courier modes.                                                              |
| Suppliers      | Search by name, campus location or tag; filter by category or location; browse suppliers nested within a parent location.                                          |
| Errands        | Create requests, accept an errand, record pickup and delivery, and confirm receipt. Cancel unassigned open requests; unaccepted requests expire at their deadline. |
| Credits        | Receive 20 starting credits, track available and reserved balances, and inspect credit history. The frontend offers a one-credit reward per errand.                |
| Administration | Manage accounts and suppliers, inspect audit logs and orders, and retry failed order-credit jobs.                                                                  |
| FAQ support    | Ask general FoC questions before or after login, inspect the supporting FAQ entries, and open suggested help questions from an order.                              |
| Responsive UI  | Use requester and courier workflows across desktop and mobile screen sizes.                                                                                        |

Credits circulate only within FoC: they cannot be bought, withdrawn, exchanged for money, or sent directly to another student. They reward the errand service; payment for items from the supplier is outside the platform.

## Getting started

**Prerequisites:** Docker Desktop with Docker Compose, plus OpenSSL for the initial JWT key setup. Ports **5173** and **8000–8004** must be available.

### First run

1. Clone the repository and enter its directory:

   ```bash
   git clone https://github.com/AY2627S1-CS3219-P16b/FoC-Template.git
   cd FoC-Template
   ```

2. Complete the [first-time setup guide](startup.md#first-time-setup-once-per-machine). It covers generating `.env` credentials and JWT keys, starting the containers, seeding suppliers, and creating the first admin.
3. Open <http://localhost:5173> and register an account. Starting credits arrive asynchronously shortly after registration.

For FAQ answers, add `ANTHROPIC_API_KEY` to the root `.env` before starting the stack. Without a key, the Help panel reports that support is temporarily unavailable. Embeddings run locally; AWS credentials are not required.

### Subsequent runs

From the repository root:

```bash
docker compose up --build -d
docker compose ps
```

To stop the stack and retain its data:

```bash
docker compose stop
```

Keep the existing `.env` when restarting: database passwords are set on first initialisation. `docker compose down -v` deletes the persistent volumes, including databases and uploaded supplier photos.

See [startup.md](startup.md) for logs, upgrades, admin bootstrap, and the optional development setup.

## Architecture

FoC contains **five FastAPI services**, **five PostgreSQL databases**, **two background workers**, and a **React frontend**. Each service owns its database; services exchange data through HTTP APIs rather than reading one another's tables.

![FoC system architecture: the React frontend calls five FastAPI services, each with its own PostgreSQL database; Order Service calls Supplier and User Services synchronously; two workers poll outbox tables and apply credit changes in Credit Service asynchronously; FAQ Service calls the Anthropic Claude API](docs/architecture.png)

Solid arrows are synchronous HTTP requests, where the caller waits for the reply. Dashed arrows are asynchronous: a job is saved in an outbox table and delivered by a worker. The diagram summarises application flows; [compose.yaml](compose.yaml) defines the container networks and mounts.

| Component          | Local port | Responsibility                                              |
| ------------------ | ---------- | ----------------------------------------------------------- |
| `frontend`         | 5173       | React UI; Vite proxies API requests to the services         |
| `user-service`     | 8000       | Accounts, roles, profiles and JWT signing                   |
| `supplier-service` | 8001       | Supplier catalogue, campus places, opening hours and images |
| `credit-service`   | 8002       | Available/reserved balances, reservations and ledger        |
| `order-service`    | 8003       | Errand lifecycle, assignments, history and credit jobs      |
| `faq-service`      | 8004       | FAQ retrieval, answer generation and request metadata       |

The frontend is the user entry point. Compose also publishes API ports on `127.0.0.1` for local access. Database ports are not published in the default setup; each database uses its service's private data network.

### Technology stack

| Layer                 | Implementation                                                             |
| --------------------- | -------------------------------------------------------------------------- |
| Frontend              | JavaScript, React 18, Vite 5                                               |
| Services and workers  | Python 3.12, FastAPI, Uvicorn                                              |
| Persistence           | PostgreSQL 17, SQLAlchemy Core, psycopg; pgvector for FAQ retrieval        |
| Authentication        | Argon2 password hashes, RS256 access tokens, rotating refresh tokens       |
| FAQ                   | Local BGE-small embeddings through FastEmbed; Anthropic Claude for answers |
| Deployment and checks | Docker Compose; pytest, unittest and the Node test runner                  |

## API documentation

The following Swagger pages are available while the local stack is running. For user-authorised endpoints, call `POST /api/v1/users/login` in the User API and use its `access_token` with **Authorize**.

FAQ chat is public. Internal credit and contact routes require the corresponding service credentials; a user JWT does not authorise them.

| Service  | Reference                                              | Local Swagger                |
| -------- | ------------------------------------------------------ | ---------------------------- |
| User     | [Endpoints and schema](user-service/README.md#api)     | <http://localhost:8000/docs> |
| Supplier | [Endpoints and schema](supplier-service/README.md#api) | <http://localhost:8001/docs> |
| Credit   | [Endpoints and schema](credit-service/README.md#api)   | <http://localhost:8002/docs> |
| Order    | [Endpoints and schema](order-service/README.md#api)    | <http://localhost:8003/docs> |
| FAQ      | [Endpoints and schema](faq-service/README.md#api)      | <http://localhost:8004/docs> |

## Testing and evaluation

Each service guide documents its test commands and prerequisites. User tests use SQLite; the Order and Supplier suites include PostgreSQL checks with separate setup requirements. FAQ unit tests use fake providers, while retrieval evaluation requires the embedding model. These checks have different scopes; they do not establish production-scale or full end-to-end coverage.

- [User tests](user-service/README.md#tests)
- [Supplier tests](supplier-service/README.md#tests)
- [Order tests](order-service/README.md#tests)
- [FAQ tests and evaluation](faq-service/README.md#tests-and-evaluation)
- Frontend checks: run `npm test` from `frontend/`.

## Team contributions

| Team member      | Main contributions                                        | Nice-to-have contributions |
| ---------------- | --------------------------------------------------------- | -------------------------- |
| Chong Yi Jie     | Supplier Service; refined frontend UI; supplier seed data | RAG-based FAQ support      |
| Jessica Ange Xu  | User Service; built initial frontend                      | None                       |
| Aurora Yufei Shi | Order Service; Credit Service                             | None                       |

Shared: each member containerised their own service and implemented its sync/async integrations.

## Repository structure

```text
.
├── user-service/       # API, registration-credit worker, tests
├── supplier-service/   # Catalogue, campus places, images, tests
├── order-service/      # API, order worker, migrations, tests
├── credit-service/     # Balances, reservations, ledger
├── faq-service/        # FAQ API, knowledge base, retrieval evaluation
├── frontend/           # React UI and frontend tests
├── data/               # Supplier seed data and original images
├── docs/               # System architecture diagram
├── compose.yaml        # 5 APIs, 2 workers, 5 databases, frontend
├── compose.dev.yaml    # Optional database ports for development
├── .env.example        # Configuration reference; generate real credentials
├── integration.md      # Service contracts and workflows
└── startup.md          # Setup, admin bootstrap and daily use
```

## License

Distributed under the [MIT License](LICENSE).

## Supporting documentation

- [Setup and run guide](startup.md)
- [Service flows and contracts](integration.md)
- [FAQ evaluation results](faq-service/evaluation/RESULTS.md)
- [AI usage log](ai/usage-log.md)

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
