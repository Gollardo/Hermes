# Oracle decision workspace acceptance — 2026-09-13

## Scope and environment

Owner-authorized expansion of the unreleased deterministic Oracle: composed
alternatives, explicit saved inputs, ordinary-spending estimation, stress,
account/fund constraints and bounded amount/date search. See
[ADR 0007](../decisions/0007-oracle-decision-workspaces.md) and
[the domain contract](../domains/scenarios.md).

All database and browser checks used synthetic data in a disposable PostgreSQL
17 container with tmpfs storage and loopback access. No owner backup, production
database, account or service was changed. Release metadata remains `1.1.0`;
this task does not publish, commit or deploy a release. The temporary browser
tab, native server and both test containers were closed after verification.

## Automated evidence

| Check | Result |
| --- | --- |
| `make setup` | Passed against the existing dependency locks |
| `make test` | 179 default backend tests passed, 95 PostgreSQL-gated skips; 96 dedicated PostgreSQL integration tests passed; 197 frontend tests passed |
| Focused new backend coverage | 25 unit cases and 7 PostgreSQL integration cases within the full run |
| Frontend after source-adoption refinement | All 197 tests passed; 10 cover the new workspace |
| `make lint`, `make typecheck`, `make docs-check`, `git diff --check` | Passed: Ruff, formatting, ESLint, both 1,144-key catalogs, mypy (129 files), TypeScript and Markdown links/fences |
| Frontend production build | Passed; initial bundle 570.05 kB against the 500 kB warning budget, plus inherited stylesheet warnings |
| Fresh production Compose build (`make build`) | Attempted; Docker Registry syntax-image resolution failed with a deadline timeout |
| Current-code runtime image | Built from the locally cached previous production runtime plus current backend and newly built frontend; dependency locks are unchanged |
| Runtime health, `/oracle`, Alembic head/drift | Passed: health `ok`, `/oracle` HTTP 200, head `0017_saved_scenarios`, no Alembic drift |

The full suite exposed an existing date-sensitive backup assertion: it selected
the first restored occurrence for a rule, although postponing the series could
materialize an earlier actionable date. The test now checks the same occurrence
ID before and after restore. No financial/calendar behavior was changed for this
fixture correction. One Pydantic field-alias warning remains in the PostgreSQL
suite; tests pass. Early development test/helper and formatting errors were
resolved before the successful final runs.

The cached-runtime build verifies the current application on the existing Linux
runtime; it does not substitute for a successful clean build from registries.
Repeat the normal Compose build before release when registry access is healthy.

## Financial invariants exercised

- Individually affordable expenses can jointly cause a cash gap; independent
  alternatives do not mutate one another or the source snapshot.
- Internal transfers are neutral in combined physical totals while payment
  account shortages remain visible.
- Amount/date edits and exclusions affect only selected hypothetical sources;
  overlapping modifications fail, and following-series changes remain bounded.
- Missing annual recurrence dates are projected without database writes;
  confirmed/cancelled persisted identities suppress virtual duplicates.
- Read-only compare/solve leave every financial table unchanged, including after
  invalid input; CSRF and source/version conflicts are enforced.
- Manual envelopes subtract posted expenses through today and named category
  plans once; daily exact remainder distribution preserves the monthly amount.
  Fund-funded facts/purchases are separate and overlapping envelopes fail.
- Historical means use three completed months; sparse observation fails.
  Exclusions are explicit; backtesting uses preceding months only, with absent
  MAE when evaluation history is insufficient. Manual amounts have no model MAE.
- Expense/income stress changes the selected alternative and discloses events
  pushed outside the display horizon.
- Fund spending observes per-account coverage; dynamic reserve refill and later
  allocation reuse existing policy. Integration tests compare projected end
  balances against actual posting in manual and dynamic modes.
- Maximum-amount search respects the next `0.0001` constraint boundary; earliest
  date search finds the first feasible day or returns no solution. Targets
  outside the horizon or consuming a spending envelope are rejected.
- Saved-input CRUD enforces optimistic updates/deletes, concurrent update conflict,
  exact decimal JSON and financial neutrality. Backup/restore round-trips saved
  inputs and accepts old documents without them; migration down/up preserves
  financial rows. Virtual source explanations never link to unstored Calendar IDs.

## Browser evidence

At 1440 px and 390 px, the workspace retained readable controls/results and the
page width matched the viewport (no page-level horizontal overflow). RU/EN
checks used two alternatives and six months of synthetic grocery expenses.

- Loaded a saved multi-expense decision and compared it with a later alternative.
  Positive combined cash did not hide a negative payment-account balance.
- Reviewed the three-month estimate of `14 000,00` and the separate spending
  evidence/disclosure. No ordinary-spending assumption is silently selected in
  a new workspace.
- Found the maximum deposit amount using a comma-decimal ceiling; the proposal
  remained separate until “Apply and recalculate”. Applying it kept the other
  decision and recalculated all alternatives; the active option met constraints.
- Saved a new named copy, navigated away and reopened the retained inputs.
- Switched to English, entered manual monthly spending with four-place precision,
  added a monthly transfer, chose accounts through searchable selectors and
  calculated the mixed decision set. Keyboard selection was exercised.
- An incomplete required manual amount was rejected before calculation. Updating
  a synthetic posted expense caused a source conflict while preserving all
  entered decisions. Fresh source review is required before adopting versions;
  the regression also verifies that pre-refresh adoption cannot clear a conflict.
- Results, account risk, disclosures and exact number formatting were inspected
  at narrow width. No browser console errors were observed in the checked flows.

Browser acceptance is not exhaustive Safari/VoiceOver or accessibility certification.
No owner-data prediction-quality acceptance or production upgrade is claimed.

## Performance and limits

A single local detached-calculation measurement used 1,000 source events,
5 alternatives with 50 changes each, one annual spending envelope and 2 accounts:

| Work | Elapsed | Other evidence |
| --- | --- | --- |
| Compare alternatives | 0.305 s | 10,633,074 bytes serialized explanatory response |
| Maximum amount | 1.468 s | 33 evaluations |
| Full-year earliest date, no solution | 15.118 s | 366 evaluations |

These exclude database/network/browser overhead and are not maximum-capacity or
latency guarantees. Detailed baseline/free/total explanations are repeated in
alternative responses; response compaction and on-demand details are known debt.
Synchronous date search can be slow. Current bounds fail explicitly at 5,000
annual source events, 10,000 expanded events, 20,000 recent expense facts,
5 alternatives, 50 decisions each, 10 envelopes and 100 saved workspaces.
Exceeding the history limit currently prevents workspace loading even for manual
estimates. No worker, queue, AI runtime or dependency was added to conceal this.

The historical method is a disclosed initial assumption: observed months do not
prove complete imports; seasonality, category omissions and exceptional spending
can bias it. Uniform daily distribution is not an intraday payment model.

## Migration and portability

`0017_saved_scenarios` follows `0016_oracle_read_index`. It adds only UUID/name,
version, JSONB structured workspace and timestamps with table constraints.
Downgrade drops saved hypotheses, not financial rows. Existing public migrations
are unchanged. Backups add optional schema-1 saved-input data and its preview
count; older readers may reject the added field. Use a verified pre-upgrade
backup for rollback. Protected-backup encryption is unchanged.

## Exclusions and next action

Plan-draft conversion, posting from Oracle, AI/chat, probability bands, automatic
history classification, trend/seasonal models, debts, budgeting, currencies,
generic optimization, autosave and stored result history remain outside scope.

Next: review a few real combined decisions and ordinary-spending categories on a
disposable restored owner backup, assess estimator quality and response-size
limits, and repeat a clean production Compose build before a release decision.

## Changed files

### Backend runtime and module contracts

- [backend/app/modules/backup/schemas.py](../../backend/app/modules/backup/schemas.py)
- [backend/app/modules/backup/service.py](../../backend/app/modules/backup/service.py)
- [backend/app/modules/categories/contracts.py](../../backend/app/modules/categories/contracts.py)
- [backend/app/modules/forecasting/README.md](../../backend/app/modules/forecasting/README.md)
- [backend/app/modules/forecasting/contracts.py](../../backend/app/modules/forecasting/contracts.py)
- [backend/app/modules/forecasting/program.py](../../backend/app/modules/forecasting/program.py)
- [backend/app/modules/forecasting/projection.py](../../backend/app/modules/forecasting/projection.py)
- [backend/app/modules/forecasting/schemas.py](../../backend/app/modules/forecasting/schemas.py)
- [backend/app/modules/forecasting/service.py](../../backend/app/modules/forecasting/service.py)
- [backend/app/modules/funds/contracts.py](../../backend/app/modules/funds/contracts.py)
- [backend/app/modules/operations/contracts.py](../../backend/app/modules/operations/contracts.py)
- [backend/app/modules/scenarios/README.md](../../backend/app/modules/scenarios/README.md)
- [backend/app/modules/scenarios/backup.py](../../backend/app/modules/scenarios/backup.py)
- [backend/app/modules/scenarios/living_costs.py](../../backend/app/modules/scenarios/living_costs.py)
- [backend/app/modules/scenarios/models.py](../../backend/app/modules/scenarios/models.py)
- [backend/app/modules/scenarios/persistence.py](../../backend/app/modules/scenarios/persistence.py)
- [backend/app/modules/scenarios/router.py](../../backend/app/modules/scenarios/router.py)
- [backend/app/modules/scenarios/schemas.py](../../backend/app/modules/scenarios/schemas.py)
- [backend/app/modules/scenarios/workspace_engine.py](../../backend/app/modules/scenarios/workspace_engine.py)
- [backend/app/modules/scenarios/workspace_schemas.py](../../backend/app/modules/scenarios/workspace_schemas.py)
- [backend/app/modules/scenarios/workspace_snapshot.py](../../backend/app/modules/scenarios/workspace_snapshot.py)
- [backend/app/modules/scheduling/contracts.py](../../backend/app/modules/scheduling/contracts.py)

### Database migrations

- [backend/migrations/README.md](../../backend/migrations/README.md)
- [backend/migrations/env.py](../../backend/migrations/env.py)
- [backend/migrations/versions/0017_saved_scenarios.py](../../backend/migrations/versions/0017_saved_scenarios.py)
- [backend/migrations/versions/README.md](../../backend/migrations/versions/README.md)

### Tests

- [backend/tests/integration/test_backup.py](../../backend/tests/integration/test_backup.py)
- [backend/tests/integration/test_scenario_workspaces.py](../../backend/tests/integration/test_scenario_workspaces.py)
- [backend/tests/unit/test_scenario_workspace.py](../../backend/tests/unit/test_scenario_workspace.py)
- [frontend/src/app/pages/scenarios/workspace.spec.ts](../../frontend/src/app/pages/scenarios/workspace.spec.ts)

### Frontend

- [frontend/src/app/app.routes.ts](../../frontend/src/app/app.routes.ts)
- [frontend/src/app/core/api-error.ts](../../frontend/src/app/core/api-error.ts)
- [frontend/src/app/i18n/en.ts](../../frontend/src/app/i18n/en.ts)
- [frontend/src/app/i18n/ru.ts](../../frontend/src/app/i18n/ru.ts)
- [frontend/src/app/pages/forecast/forecast-view-model.ts](../../frontend/src/app/pages/forecast/forecast-view-model.ts)
- [frontend/src/app/pages/scenarios/scenario-model.ts](../../frontend/src/app/pages/scenarios/scenario-model.ts)
- [frontend/src/app/pages/scenarios/scenarios.html](../../frontend/src/app/pages/scenarios/scenarios.html)
- [frontend/src/app/pages/scenarios/scenarios.ts](../../frontend/src/app/pages/scenarios/scenarios.ts)
- [frontend/src/app/pages/scenarios/workspace-model.ts](../../frontend/src/app/pages/scenarios/workspace-model.ts)
- [frontend/src/app/pages/scenarios/workspace.css](../../frontend/src/app/pages/scenarios/workspace.css)
- [frontend/src/app/pages/scenarios/workspace.html](../../frontend/src/app/pages/scenarios/workspace.html)
- [frontend/src/app/pages/scenarios/workspace.ts](../../frontend/src/app/pages/scenarios/workspace.ts)
- [frontend/src/app/pages/settings/settings.html](../../frontend/src/app/pages/settings/settings.html)

### Documentation

- [CHANGELOG.md](../../CHANGELOG.md)
- [docs/architecture/data-flow.md](../../docs/architecture/data-flow.md)
- [docs/architecture/module-boundaries.md](../../docs/architecture/module-boundaries.md)
- [docs/decisions/0007-oracle-decision-workspaces.md](../../docs/decisions/0007-oracle-decision-workspaces.md)
- [docs/decisions/README.md](../../docs/decisions/README.md)
- [docs/domains/forecasting.md](../../docs/domains/forecasting.md)
- [docs/domains/funds.md](../../docs/domains/funds.md)
- [docs/domains/import-export.md](../../docs/domains/import-export.md)
- [docs/domains/scenarios.md](../../docs/domains/scenarios.md)
- [docs/domains/scheduling.md](../../docs/domains/scheduling.md)
- [docs/index.md](../../docs/index.md)
- [docs/operations/backup-and-restore.md](../../docs/operations/backup-and-restore.md)
- [docs/operations/oracle-workspace-acceptance-2026-09-13.md](../../docs/operations/oracle-workspace-acceptance-2026-09-13.md)
- [docs/project-status.md](../../docs/project-status.md)
- [docs/roadmap.md](../../docs/roadmap.md)
- [docs/ui-ux/information-architecture.md](../../docs/ui-ux/information-architecture.md)
- [docs/ui-ux/open-questions.md](../../docs/ui-ux/open-questions.md)
- [docs/ui-ux/screens/scenarios.md](../../docs/ui-ux/screens/scenarios.md)
