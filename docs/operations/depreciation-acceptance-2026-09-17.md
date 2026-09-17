# Replacement savings acceptance — 2026-09-17

The owner-authorized vertical slice is implemented and remains unreleased.
No production database was accessed or migrated.

## Verified behavior

- A purchase of RUB 200,000.00, a 36-month term and 10% expected annual
  inflation produces a RUB 266,200.00 target and a RUB 7,394.44 displayed
  first monthly requirement. Saving starts after the purchase month.
- A RUB 5,000.00 contribution leaves the current month's requirement unchanged
  and displays RUB 2,394.44 remaining. Future monthly requirements use actual
  accumulated savings. A closed month's shortfall is redistributed.
- Contributions can reserve free money or combine a physical transfer and a
  reservation atomically. Releases return savings to free money.
- Ordinary funds and replacement savings share physical accounts without
  reserving the same money twice. Their summary amounts are shown separately.
- Preview, creation, contribution, details, history linkage and the Funds
  summary were exercised in a browser with synthetic data. At 390 px the
  document had no horizontal overflow. Modal focus containment, reverse Tab,
  Escape and focus restoration were checked.

## Automated checks

- Default backend test stage: 149 passed, 105 PostgreSQL-gated tests skipped.
- PostgreSQL 17 integration stage: 106 passed.
- Frontend: 25 files, 186 tests passed on the final frontend rerun.
- Ruff, Python formatting, Angular lint, RU/EN catalog completeness, Prettier,
  documentation links, mypy and TypeScript checks passed.
- Production frontend and Docker builds passed. The final image passed health,
  served `/depreciation` with HTTP 200 and passed `alembic check` at migration
  `0017_depreciation` with no metadata differences.
- The aggregate test command's backend stages passed; frontend assertions were
  corrected for focus containment and the expanded coverage explanation, and
  the full frontend suite was rerun successfully.

Tests cover inflation and fractional years, exact decimal rounding, month and
leap-year boundaries, partial/missed/extra contributions, final remainder,
expiry, release and early funding. Integration coverage includes atomicity,
coverage limits, stale versions, concurrent idempotent retries, linked-operation
protection, ordinary/dynamic fund isolation, authentication and CSRF,
backup validation and restore, migration consistency and guarded downgrade.

## Limits and follow-up

The initial production bundle is 544.52 kB against the 500 kB warning budget;
inherited component stylesheet warnings remain. A Pydantic warning in the
concurrent Funds integration test remains non-failing. No dependency or runtime
infrastructure was added.

The initial implementation locks accounts broadly for consistent reservation
writes and returns complete purchase schedules/history. Pagination and narrower
locking are future scaling work. Terms are bounded to 600 months and expected
annual inflation to 0–100%; these are implementation limits, not a forecast.

Scope excludes editing purchase assumptions after creation, backdated
contributions, reopening archives, automatic deadline extensions, batch
allocation, daily forecast/calendar integration, purchase matching and bank
execution. Replacement expenses remain ordinary explicit operations.

Next: review the feature against an isolated restored owner backup, retain a
pre-upgrade backup, and separately authorize release/deployment. Downgrade is
refused while replacement purchase records exist; rollback requires the
pre-upgrade backup rather than deleting financial history.
