# Oracle acceptance — 2026-09-11

## Scope and environment

This is an unreleased implementation record, not a publication or production
upgrade record. The owner requested the full bounded deterministic Oracle slice.
The starting checkout was `8f3dbed`, including the unreleased statement-import
work and migration `0015_statement_imports`.

Tests used a disposable PostgreSQL 17 Alpine container on loopback port 55436
with tmpfs storage and isolated per-test databases. Browser fixtures contained
only synthetic accounts, funds and plans. Native FastAPI on port 8016 first
served the production frontend; the final Compose-built image was then started
independently on port 8017 against the disposable preview database. No owner
backup or production service was used or changed.

## Automated evidence

| Check | Result |
| --- | --- |
| Default backend suite (`make test-backend`) | 154 passed, 88 PostgreSQL-gated tests skipped |
| PostgreSQL suite (`make test-backend-postgres`) | 89 passed on PostgreSQL 17 |
| Frontend suite (`npm test --prefix frontend`) | 187 passed |
| Focused Oracle frontend after typed provenance refinement | 9 passed |
| `make lint` | Ruff, formatting, ESLint, catalogs and docs passed |
| `make typecheck` | mypy and TypeScript passed |
| Frontend production build | Passed; inherited/eager-catalog budget warnings |
| Production Compose build | Passed |
| Built-image health and `/oracle` | `ok` and HTTP 200 |
| Built-image `alembic check` | No new upgrade operations at `0016_oracle_read_index` |
| Index downgrade to 0015 and upgrade to head | Passed; expected occurrences preserved |
| `git diff --check` | Passed |

The Makefile's three test targets cover its complete `make test` composition.
Default and PostgreSQL test totals are separate runs, not additive code coverage.
The final display-range caption refinement passed focused frontend tests (9),
catalog/formatting checks, type checks and a rebuilt production image.

## Domain invariants exercised

- Exact decimal inputs, no floats/non-finite values, scale/envelope limits,
  positive amounts, complete command shape and unknown-field rejection.
- No-op overlays and order-independent source iteration; no input mutation;
  deterministic repeated comparisons; one occurrence rather than a series edit.
- Date bounds and horizon crossing in both directions; daily cash gaps retained
  under monthly annual aggregation, same-day starting deficit/recovery and
  strictly-below thresholds, including exact equality and unrecovered windows.
- Read-only database enforcement and unchanged financial rows after successful
  or failed scenario calculations. Source reads do not materialize missing plans.
- MVCC consistency while confirmation, postponement, actual posting, new-plan
  creation and fund allocation commit concurrently. A confirming occurrence is
  not counted twice. Later requests identify the changed source state.
- Source identity/version conflicts, account validity and comparison scope.
- Physical transfer neutrality, globally ordered dynamic distributions,
  downstream per-fund changes even when total allocation is unchanged, and
  overflow reserve reducing free money while physical total remains unchanged.
- Baseline agreement with the existing Forecast API and agreement with actual
  confirmation of a dynamically allocated transfer with reserve overflow.
- CSRF/authentication, recoverable network/source errors, exact comma/dot inputs,
  stale-response rejection, reset, RU/EN preservation and synthetic-source labels.

## Browser scenarios

Synthetic initial physical balance: 100,000; fund allocation: 20,000; free money:
80,000. Rent: 40,000 on September 12; salary: 60,000 on September 21.

- A purchase of 50,000.0001 on September 14 produced the expected negative free
  minimum and September 21 recovery. Moving it to September 22 removed the cash
  gap while preserving the end-period delta.
- Replacing the selected rent amount with 45,000.0001 decreased the minimum and
  period-end money by 5,000.0001 without modifying the source plan. User boundary
  38,000 and system boundary 40,000 were displayed separately.
- Moving the selected rent occurrence beyond the monthly horizon increased the
  displayed period-end balance and explicitly disclosed the out-of-horizon effect.
- A new income of 30,000.0001 increased free/total end balances; the English
  view retained canonical comma-based monetary presentation.
- Source choices showed account, amount and date. Changed-source detail was a
  hypothesis; its original plan remained linkable separately.
- A risk action selected its exact minimum day, moved focus to the comparison
  section and showed opening/closing balances with source explanations.
- Leaving Oracle and returning discarded the temporary input/results. Account
  combobox selection and calculation submission were exercised by keyboard.
- Desktop (1440 px) and narrow (390 px) layouts retained financial content. The
  document scroll width equaled the viewport width. The medium-width form was
  refined to use its available width rather than a fixed three-column layout.
- Both RU and EN were checked; automated tests additionally verify changing
  language while retaining draft values and refreshing a stale source.

Native date/select controls retain platform behavior. These checks do not claim
exhaustive Safari, mobile-device or screen-reader certification.

## Migration, compatibility and limits

`0016_oracle_read_index` adds only the actionable-occurrence due-date/identity
index. Published migrations are unchanged, schema-1 backups remain compatible,
and no saved scenario or conversation table exists. The index can briefly block
schedule writes during creation. Use a protected backup and a maintenance
upgrade; do not infer a production migration from this disposable test.

The common forecast's omission of dynamic overflow reserve was corrected and
regression-tested against actual posting. Existing Forecast response fields are
preserved; event provenance is additive. Public read contracts add versions and
optional lock-free reads while retaining existing locking defaults.

Unimplemented: multiple decisions, saved alternatives, plan-draft conversion,
fund-funded synthetic expenses, series edits, automatic plan materialization,
AI/chat, historical or probabilistic prediction, debts, budgets and FX. Sparse
plans cannot justify an inferred spending history. The suggested drawdown buffer
is explicitly a bounded heuristic. Large annual snapshots and explanations need
measured performance work; no source events are silently truncated. The initial
bundle remains above the 500 kB warning threshold (approximately 545 kB), partly
because both translation catalogs ship eagerly.

## Next action

Owner review of several decisions against a disposable restored backup, followed
by a separate release/version decision. Production deployment and publication
remain outside this task. Saved-scenario design is the next product scope.


## Changed-file inventory

Paths are relative to the repository root.

```text
CHANGELOG.md
backend/app/api/router.py
backend/app/core/database.py
backend/app/modules/forecasting/README.md
backend/app/modules/forecasting/contracts.py
backend/app/modules/forecasting/projection.py
backend/app/modules/forecasting/schemas.py
backend/app/modules/forecasting/service.py
backend/app/modules/funds/contracts.py
backend/app/modules/funds/service.py
backend/app/modules/scenarios/README.md
backend/app/modules/scenarios/__init__.py
backend/app/modules/scenarios/router.py
backend/app/modules/scenarios/schemas.py
backend/app/modules/scenarios/service.py
backend/app/modules/scenarios/snapshot.py
backend/app/modules/scheduling/contracts.py
backend/app/modules/scheduling/models.py
backend/migrations/README.md
backend/migrations/versions/0016_oracle_read_index.py
backend/tests/integration/test_scenarios.py
backend/tests/unit/test_scenario_calculation.py
docs/architecture/data-flow.md
docs/architecture/module-boundaries.md
docs/decisions/0006-deterministic-oracle.md
docs/decisions/README.md
docs/domains/forecasting.md
docs/domains/funds.md
docs/domains/scenarios.md
docs/domains/scheduling.md
docs/index.md
docs/operations/oracle-acceptance-2026-09-11.md
docs/project-status.md
docs/roadmap.md
docs/ui-ux/information-architecture.md
docs/ui-ux/open-questions.md
docs/ui-ux/screens/forecast.md
docs/ui-ux/screens/scenarios.md
frontend/src/app/app.html
frontend/src/app/app.routes.ts
frontend/src/app/core/api-error.ts
frontend/src/app/i18n/en.ts
frontend/src/app/i18n/ru.ts
frontend/src/app/pages/forecast/forecast-view-model.ts
frontend/src/app/pages/forecast/forecast.html
frontend/src/app/pages/scenarios/scenario-model.ts
frontend/src/app/pages/scenarios/scenarios.css
frontend/src/app/pages/scenarios/scenarios.html
frontend/src/app/pages/scenarios/scenarios.spec.ts
frontend/src/app/pages/scenarios/scenarios.ts
```
