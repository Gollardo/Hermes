# Multi-day statement import acceptance, 2026-10-21

## Outcome

The integrated CSV/XLSX workflow is implemented and regression-green at its
automated boundaries. A representative authenticated CSV scenario covers
write-free preview, profile persistence, confirmation, retry identity,
operation editing without provenance loss, journal readback, export, restore,
rollback and destructive-downgrade protection. A literal deterministic
multi-day XLSX scenario covers authentication, profile persistence, write-free
preview, the source dates needed for browser-local inclusive filtering, per-row
plan and existing-fact candidate queries, chronological new/plan/existing
confirmation, operation-detail provenance, schema-1 export, restore and exact
readback. Component tests separately cover searching candidates by localized
and ISO dates and the completed-row journal link; the API scenario does not
claim to click that link in a browser.

The broader suites retain source-period filtering, searchable category/plan/fact
reconciliation, missing/invalid/future date rejection without fallback,
outside-period warnings, new/plan/group/existing description ownership,
chronological posting, the 200-row limit, exact decimal values, atomic rollback,
stale conflicts, fund coverage and backup compatibility. Component tests retain
the RU/EN, keyboard, focus, hierarchy, long-label, large-amount,
candidate-date localization, transfer-direction refresh and responsive
presentation contracts.

`CandidateRequest.source_description` now accepts the same maximum 4,000
characters as parsed cells, receipt persistence and schema-1 backup validation.
An authenticated HTTP boundary test accepts 4,000 characters and rejects 4,001;
the server does not invent or truncate provenance.

## Verification

- Default backend suite: 223 passed, 128 PostgreSQL-gated tests skipped.
- PostgreSQL integration suite: 129 passed against randomly named disposable
  databases, including the authenticated CSV and XLSX lifecycle scenarios.
- The available host runs unsupported Node.js 26.10.0 and npm 11.19.1; the
  documented development environment is Node.js 22.22.3 within the Node 22
  release line and npm 10. Plain `make test-frontend` fails broadly because
  Node 26's experimental global local storage masks jsdom's implementation.
- With the Node 26 compatibility flag
  `NODE_OPTIONS=--no-experimental-webstorage make test-frontend`, all 212
  frontend tests passed across all 25 files in the standard parallel runner.
  The focused import component suite passed all 21 tests after correcting the
  RU/EN source-date introduction. Supported Node 22 was not tested in this run.
- Ruff lint and format, ESLint, RU/EN catalog completeness, Prettier, mypy,
  TypeScript and documentation link/fence checks passed.
- The production frontend build passed. Existing initial-bundle and component
  style-budget warnings remain unchanged; no budget was raised.
- A fresh named disposable database upgraded from an empty schema through
  `0018_import_provenance`; `alembic check` reported no new upgrade operations.
  Automated migration coverage also verifies legacy receipt defaults,
  downgrade/re-upgrade parity and refusal to discard populated provenance.

## Browser and external gates

A later browser run used a local disposable PostgreSQL database and a synthetic
multi-day CSV. The complete Russian desktop flow verified the inclusive source
period and excluded count, restoration of a hidden edited draft, keyboard
category search, the out-of-period posting warning, chronological summary,
atomic confirmation, success only after the response, journal links and source
provenance in operation details. At 390 px the Russian and English layouts had
equal document `clientWidth` and `scrollWidth`; the same was true for English at
1440 px. The checked pages emitted no console warning or error.

This evidence does not cover browser interaction with the literal XLSX fixture,
real-device/Safari assistive technology, PostgreSQL 17 Compose, production
deployment, owner data or owner visual acceptance. Those gates remain open.

No owner statement or backup was available for either run. The conditional
isolated-owner-data scenario was therefore not performed. No private fixture,
screenshot, production database or production service was read or modified.
