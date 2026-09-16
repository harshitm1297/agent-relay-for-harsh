# Agent Relay v2 — Homework 3

Agent Relay is a small FastAPI service for registering agents, delivering one
task at a time, and recording results. Workers execute tasks on their own
machines; the included worker deterministically returns `input.upper()`.

This fork completes Homework 3 of the AI Dev Tools Zoomcamp. It supports the
starter's local SQLite mode plus PostgreSQL, Docker Compose, Kubernetes on
kind, a real-API acceptance test, and a test-gated CI/deployment workflow.

## Architecture

```text
sender agent ─┐                         ┌─ PostgreSQL
              ├─ HTTP API / dashboard ─┤
worker agent ─┘                         └─ task and attempt records
```

Agents claim tasks through the API. The relay does not execute submitted text
and does not need an LLM or message broker. SQLite serializes writers with
`BEGIN IMMEDIATE`; PostgreSQL claims available rows with
`SELECT ... FOR UPDATE SKIP LOCKED` so concurrent workers do not receive the
same active task.

## Prerequisites

- `uv` for direct Python development
- Docker Desktop with Linux containers and Docker Compose
- `kind` and `kubectl` for the Kubernetes exercise
- `act` for running the GitHub Actions workflow locally

Verify them with:

```bash
uv --version
docker version
docker compose version
kind version
kubectl version --client
act --version
```

## Run directly with SQLite

```bash
uv sync
uv run uvicorn main:app --reload
```

Open <http://127.0.0.1:8000/> for the token-based local dashboard. The default
database is `./agent-relay.db`; set `RELAY_DATABASE_URL` to use another SQLite
file. `GET /health` is a liveness check and `GET /ready` verifies database
connectivity and schema (it queries the real tables, so a wiped volume
reports not-ready instead of passing with zero tables).

Register two identities and send a task:

```bash
alice=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/agents \
  -H 'content-type: application/json' -d '{"name":"alice"}')
bob=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/agents \
  -H 'content-type: application/json' -d '{"name":"uppercase"}')
```

The response contains each agent's secret `token` once. Keep it outside source
control. Use `Authorization: Bearer <token>` for all subsequent API calls;
registration is the only unauthenticated endpoint. For a shared installation,
set `RELAY_ENROLLMENT_SECRET` and send it as `X-Enrollment-Secret` when
registering.

## Run the deterministic worker

The worker can register itself and save credentials in a mode-0600 JSON file:

```bash
uv run python main.py worker \
  --base-url http://127.0.0.1:8000 \
  --name uppercase \
  --credentials ./uppercase-credentials.json \
  --worker-id laptop-1
```

For failure/redelivery demonstrations, make local execution intentionally slow
and stop the process after one completion:

```bash
uv run python main.py worker --credentials ./uppercase-credentials.json \
  --slow-seconds 75 --worker-id slow-laptop
```

The worker heartbeats during long work. Killing it leaves the claim leased;
after the 60-second lease expires, another worker can claim the task with a new
token and incremented attempt number. `RELAY_LEASE_SECONDS` and
`RELAY_MAX_ATTEMPTS` are configurable server settings.

An existing credential can also be supplied explicitly (the token is not
written to disk):

```bash
uv run python main.py worker --agent-id agent_123 --token agt_… --worker-id laptop-2
```

## Storage and delivery behavior

`database.py` contains SQLAlchemy models and database-specific transaction
setup. `storage.py` contains task/claim/recovery operations; routes and request
models are kept in `main.py` and `schemas.py`. The HTTP protocol and lifecycle
in `SPEC.md` remain identical across SQLite and PostgreSQL.

Claims are at-least-once and leased for 60 seconds by default. Heartbeats extend
an active lease. A completion or failure must include the recipient's bearer
token and claim token. Repeating the exact terminal request with that claim
token is idempotent; a stale token or different result receives `409`.

## Test locally

The test suite covers the main protocol, sender/recipient access boundaries,
hashed claim-token behavior, idempotent terminal retries, concurrent claims,
lease expiry before and after recovery, pagination/error shape, and dashboard
asset serving:

```bash
uv run pytest -q
```

Tests default to a scratch database at `./agent-relay-test.db` so they don't
reset your dev server's `./agent-relay.db`. The fixture drops and
recreates all tables on whatever `RELAY_DATABASE_URL` points at, so stop
the dev server first or set `RELAY_DATABASE_URL` to a scratch file before
running tests against another database.

The separate acceptance test targets a running API and its real database:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
# in another terminal
uv run pytest -q tests/integration
```

It registers two agents, sends and claims a task, submits the result, and proves
that the sender sees `completed` with the expected output.

## Docker image

Build the required image and publish its API port:

```bash
docker build -t agent-relay:local .
docker run --rm -p 8000:8000 -v agent-relay-data:/data agent-relay:local
```

Open <http://127.0.0.1:8000/> and repeat the task flow. The standalone image
uses SQLite in the named volume. Uvicorn binds to `0.0.0.0`, which makes the
published port reachable.

## Docker Compose with PostgreSQL

```bash
docker compose up --build -d
docker compose ps
uv run pytest -q tests/integration
```

The API connects to the database hostname `postgres`, the Compose service name.
Open <http://127.0.0.1:8000/>. To stop without deleting data:

```bash
docker compose down
```

Use `docker compose down --volumes` only when you intentionally want to delete
the local PostgreSQL data.

## Kubernetes with kind

Create a local cluster, load the image into it, and apply the manifests:

```bash
kind create cluster --name agent-relay
docker build -t agent-relay:local .
kind load docker-image agent-relay:local --name agent-relay
kubectl apply -f k8s/
kubectl -n agent-relay rollout status statefulset/postgres --timeout=180s
kubectl -n agent-relay rollout status deployment/agent-relay --timeout=180s
kubectl -n agent-relay get pods,services,pvc
```

Forward the Service and open the dashboard:

```bash
kubectl -n agent-relay port-forward service/agent-relay 8000:8000
```

Then visit <http://127.0.0.1:8000/> and run the integration test in another
terminal. The PostgreSQL StatefulSet stores data in a persistent volume claim.

Delete the exercise cluster when finished:

```bash
kind delete cluster --name agent-relay
```

## CI/CD with `act`

`.github/workflows/ci.yml` runs the starter tests against PostgreSQL, launches
the real API for the acceptance test, and only then builds an immutable image
tag and deploys it to a temporary kind cluster. Its final check opens the
deployed dashboard and requires the heading `Agent Relay v2`.

With Docker Desktop running, execute:

```bash
act push --container-architecture linux/amd64
```

If a test fails, the dependent deployment job is skipped and the existing
version remains untouched. No cloud credentials or LLM key are required.

## Homework answers

See [`HOMEWORK_ANSWERS.md`](HOMEWORK_ANSWERS.md).
