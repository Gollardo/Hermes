<div align="center">

# Hermes

**A self-hosted personal finance command center for exact accounting, purposeful
savings, planned operations, and explainable cash forecasting.**

[![Status: stable](https://img.shields.io/badge/status-stable-347A5A)](docs/project-status.md)
[![Self-hosted](https://img.shields.io/badge/deployment-self--hosted-347A5A)](docs/operations/deployment.md)
[![License: AGPL-3.0-or-later](https://img.shields.io/badge/license-AGPL--3.0--or--later-4C6EF5)](LICENSE)

</div>

![Hermes overview showing free money, physical balance, reserved funds, near-term forecast, and category analytics](docs/assets/readme/overview.jpg)

Screenshots show the English interface from the upcoming `1.1.0` release with
synthetic USD demonstration data; no personal financial data is included.

Hermes helps one owner understand not only where money went, but what is free to
use, what has already been assigned to goals, and how known plans may change the
future balance. It runs on your own computer or home server, stores data in your
PostgreSQL database, and does not depend on an external cloud service.

> [!IMPORTANT]
> Hermes `1.0.0` is the first public release. It supports a single owner in a
> protected environment: loopback or a trusted network, with VPN or a maintained
> HTTPS reverse proxy for remote access. Direct public-internet exposure remains
> unsupported.

## Why Hermes

- **Free money first.** Physical balance, virtual funds, account reserves, and
  genuinely free money remain distinct instead of collapsing into one total.
- **The future is explainable.** Forecast points are derived from current
  balances and known planned events, with the exact events behind each change.
- **Financial operations stay exact.** Money uses `Decimal`/`NUMERIC`, writes are
  transactional, and displayed values follow one deterministic formatting and
  rounding contract.
- **Your data stays yours.** Hermes is single-owner and self-hosted, with
  protected `.hermes` backups and an explicit plaintext JSON option.

## Product tour

### Understand the next month

Forecast free or total money across five horizons, inspect the minimum balance,
cash-gap risk, net flow, and every event that changes the projection.

![Hermes balance forecast with period controls, decision metrics, and an explainable timeline](docs/assets/readme/forecast.jpg)

### Give saved money a purpose

Virtual funds reserve parts of real account balances for goals without creating
separate bank accounts. Hermes tracks progress, physical coverage, free money,
and manual or dynamic allocation.

![Hermes virtual funds showing saved totals, free money, allocation mode, and goal progress](docs/assets/readme/funds.jpg)

### Plan without changing today's balance

Recurring rules and one-off plans stay balance-neutral until they are confirmed.
The calendar shows exact dated amounts and keeps overdue actions explicit.

![Hermes calendar showing recurring income, expenses, and one-off plans](docs/assets/readme/calendar.jpg)

<details>
<summary><strong>Responsive interface</strong></summary>

Hermes adapts its navigation and content hierarchy for narrow screens rather
than shrinking the desktop layout mechanically.

<p align="center">
  <img src="docs/assets/readme/overview-mobile.jpg" width="390" alt="Hermes overview on a narrow mobile viewport">
</p>

</details>

The development version supports Russian and English, with a browser-local
language preference. Multilingual support is implemented for the upcoming
`1.1.0` release; the latest public release remains `1.0.0`.

## Current capabilities

### Everyday finance

- cash, debit, and savings accounts with ledger-derived balances;
- income, expense, transfer, and balance-adjustment operations;
- required income/expense categories, nested category trees, and archive-safe
  historical references;
- journal filtering, details, pagination, category reports, and monthly or
  custom reporting periods;
- exact addition and subtraction directly in monetary inputs.

### Funds and available money

- virtual funds backed by money on physical accounts;
- per-account physical, fund-reserved, reserve, and free coverage;
- manual percentages or dynamic allocation based on relative unfilled progress;
- atomic allocation, redistribution, fund-to-fund movement, and fund-aware
  account transfers;
- target caps, automatic reserve refill, and deterministic rounding.

### Planning and forecasting

- recurring income, expense, and transfer rules;
- one-off future plans that remain balance-neutral until applied;
- monthly calendar, upcoming and overdue states, confirmation, postponement,
  cancellation, and optional recurring-series shifting;
- per-account and combined forecasts across two weeks, one month, one quarter,
  six months, or one year;
- free-money and total-balance modes, risk warnings, and exact event explanations.

### Access and data protection

- atomic first-run setup or restore, master password, base currency, and IANA
  timezone;
- Argon2id password storage, revocable server-side sessions, CSRF protection,
  login throttling, and idle-session expiry;
- authenticated `.hermes` backup envelopes plus explicit plaintext JSON export;
- previewed, validated, transactional restore.

See the [current project status](docs/project-status.md) for the factual
verification snapshot, known limitations, and the next release gate.

## Run locally

The shortest production-like path requires Docker 29+ with Docker Compose v2
and `make`.

```bash
cp .env.example .env
# Replace POSTGRES_PASSWORD in .env.
# For loopback-only plain HTTP, set HERMES_COOKIE_SECURE=false.
make up
```

Open `http://localhost:8000`. Angular and the API share one HTTP entrypoint, and
PostgreSQL remains inside the Compose network. Stop the application with
`make down`.

> [!WARNING]
> Do not expose an uninitialized Hermes instance or PostgreSQL directly to the
> internet. Remote access requires a protected network, VPN, or a maintained
> HTTPS reverse proxy with secure cookies enabled. Read the
> [security policy](SECURITY.md) before using real financial data.

## Development

Requirements: Python 3.13, Node.js 22.22.3 or newer within the supported Node 22
line, npm, Docker Compose, and `make`.

```bash
cp .env.example .env
make setup
make dev
```

Open `http://localhost:4200`. The Angular development server proxies `/api` to
FastAPI on `http://localhost:8000`.

Run the complete local quality gates with:

```bash
make test
make lint
make typecheck
```

The [local development guide](docs/operations/local-development.md) documents
individual commands, dependency changes, migrations, and disposable PostgreSQL
integration tests.

## Architecture

Hermes is a modular monolith: one deployable application, one PostgreSQL
database, and explicit public boundaries between financial domains.

```mermaid
flowchart LR
    Browser[Owner browser] --> Entry[Single HTTP entrypoint]
    Entry --> Angular[Angular application]
    Entry --> API[FastAPI modular monolith]
    API --> Domains[Domain modules]
    Domains --> PostgreSQL[(PostgreSQL)]
```

- Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic, and PostgreSQL;
- Angular 22 with standalone components and strict TypeScript;
- pytest, Ruff, mypy, ESLint, Prettier, and Vitest;
- Docker and Docker Compose;
- no microservices, broker, background worker, Redis, Kubernetes, or external
  cloud data dependency.

Read the [architecture overview](docs/architecture/overview.md),
[module boundaries](docs/architecture/module-boundaries.md), and
[data flows](docs/architecture/data-flow.md) before changing cross-domain
behavior.

## Status and roadmap

Hermes is a personal project whose direction follows the maintainer's own use.
Version `1.0.0` is the first stable public release. Compatibility and release
operations are documented in the [release lifecycle](docs/operations/release.md).

The long-term north star is **Oracle · What if?**: deterministic temporary
scenarios that compare a financial decision with the baseline forecast without
changing the ledger or confirmed plan. Oracle is planned and is not part of the
current release.

- [Current project status](docs/project-status.md)
- [Development roadmap](docs/roadmap.md)
- [Changelog](CHANGELOG.md)

## Documentation and support

- [Documentation map](docs/index.md)
- [UI/UX contract](DESIGN.md)
- [Deployment runbook](docs/operations/deployment.md)
- [Backup and restore](docs/operations/backup-and-restore.md)
- [Security policy](SECURITY.md)

For defects and focused proposals, use the
[GitHub issue tracker](https://github.com/Gollardo/hermes/issues). Do not include
credentials, backup contents, or personal financial data in an issue.

## Contributing

Issues and pull requests are welcome when they align with the project's
direction, but there is no guaranteed response or review schedule. Keep changes
small, preserve module boundaries and financial invariants, and include checks
appropriate to the risk.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before starting implementation.

## License

Copyright holders license Hermes under the
[GNU Affero General Public License v3.0 or later](LICENSE), SPDX identifier
`AGPL-3.0-or-later`.
