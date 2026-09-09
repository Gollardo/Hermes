# Local development

## Prerequisites

- Python 3.13;
- Node.js 22.22.3+ within the Node 22 release line and npm 10+;
- Docker 29+ with Docker Compose v2-compatible CLI;
- GNU or BSD `make` and Git.

The versions above match the initialized environment. Angular's exact packages
are locked in `frontend/package-lock.json`; Python packages are hash-locked in
`backend/requirements*.lock`.

## Initial setup

```bash
cp .env.example .env
# Replace POSTGRES_PASSWORD before any non-local deployment.
make setup
```

`make setup` creates `.venv`, installs hash-verified backend development
dependencies and runs `npm ci`. Environment-file creation stays explicit so the
developer reviews the example before using its placeholder password.

## Development servers

```bash
make dev
```

This starts PostgreSQL, the FastAPI reload server at `http://localhost:8000`,
and Angular at `http://localhost:4200`. The Angular proxy forwards `/api` to the
backend, so application code uses a same-origin relative API base URL.
The proxy target defaults to host `localhost:8000`; development Compose sets
`HERMES_PROXY_TARGET=http://backend:8000` for container-to-container routing.

## Command interface

| Command | Effect |
| --- | --- |
| `make setup` | create local environment and install locked dependencies |
| `make dev` | foreground development Compose stack |
| `make up` | build/start production-like stack in background |
| `make down` | stop production and development stacks |
| `make logs` | follow production app/PostgreSQL logs |
| `make test` | all backend and frontend tests, including PostgreSQL integration |
| `make test-backend` | pytest with coverage |
| `make test-backend-postgres` | access/migration integration tests against disposable databases on a test PostgreSQL server |
| `make test-frontend` | Angular/Vitest unit tests once |
| `make lint` | Ruff, formatting, ESLint, Prettier and docs links/fences |
| `make format` | apply Ruff and Prettier formatting |
| `make typecheck` | strict mypy and TypeScript checks |
| `make migrate` | apply Alembic revisions |
| `make migration name="..."` | autogenerate a reviewable revision |
| `make build` | build the production Compose image |

## Changing dependencies

Edit `backend/pyproject.toml`, then regenerate both lock files from a temporary or
existing environment containing `pip-tools`:

```bash
.venv/bin/pip-compile --generate-hashes --strip-extras \
  --output-file backend/requirements.lock backend/pyproject.toml
.venv/bin/pip-compile --generate-hashes --strip-extras --extra dev \
  --output-file backend/requirements-dev.lock backend/pyproject.toml
```

For frontend dependencies, use npm and commit both `package.json` and
`package-lock.json`. Use `npm ci`, not an unlocked install, in verification and
containers. The `overrides` pin transitive MCP SDK, Hono and Nano ID versions in
Angular build tooling. Recheck both their compatibility and current audit status
during Angular upgrades; the latest verified result is recorded in
`docs/project-status.md`.

## Migrations

Run Alembic from `backend` through the Make targets. The current single head is
`0014_one_off_plans`; [the migration registry](../../backend/migrations/README.md)
records the chain and destructive downgrade consequences. Never rewrite a
published revision; correct it with a new migration.

`make test-backend` keeps PostgreSQL scenarios opt-in so an isolated backend unit
run does not create or drop databases. The aggregate `make test` and explicit
`make test-backend-postgres` targets require a dedicated PostgreSQL server whose
test role may create databases. Point these variables at that server:

```bash
HERMES_TEST_DATABASE_HOST=127.0.0.1 \
HERMES_TEST_DATABASE_PORT=5432 \
HERMES_TEST_DATABASE_USER=hermes \
HERMES_TEST_DATABASE_PASSWORD=test-only-password \
make test-backend-postgres
```

Each test creates a randomly named `hermes_test_*` database, migrates it and
drops only that database with `FORCE` during teardown. Never point the test
credentials at a role that should not create disposable databases.
