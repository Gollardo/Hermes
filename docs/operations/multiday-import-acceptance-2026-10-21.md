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
- Frontend suite: 211 passed across all 25 spec files when run sequentially,
  each process using an isolated Node local-storage file.
- The standard parallel frontend command reached 208 of 211 tests; its three
  failures are the known cross-file local-storage/combobox race, not deterministic
  product failures. The focused import component suite passed all 20 tests.
- Ruff lint and format, ESLint, RU/EN catalog completeness, Prettier, mypy,
  TypeScript and documentation link/fence checks passed.
- The production frontend build passed. Existing initial-bundle and component
  style-budget warnings remain unchanged; no budget was raised.
- A fresh named disposable database upgraded from an empty schema through
  `0018_import_provenance`; `alembic check` reported no new upgrade operations.
  Automated migration coverage also verifies legacy receipt defaults,
  downgrade/re-upgrade parity and refusal to discard populated provenance.

## Browser and external gates

Browser servers were started against the fresh disposable database, but the
available in-app browser provider was unavailable and native Safari attachment
hung before any page could be observed. The hanging attachment was stopped; it
is not evidence of a product failure. This review-fix pass made a bounded
provider inventory attempt and found no attached browser provider. Consequently the required real-browser
RU/EN desktop and 390 px run, visible-focus and horizontal-overflow observations
remain open. Real-device/Safari assistive-technology, PostgreSQL 17 Compose,
production deployment and owner visual acceptance also remain open.

No owner statement or backup was available for this run. The conditional
isolated-owner-data scenario was therefore not performed. No private fixture,
screenshot, production database or production service was read or modified.
