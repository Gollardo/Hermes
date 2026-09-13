# Project status

Last reviewed: 2026-09-13. This is the current release snapshot, not a task log.
Detailed history belongs in [CHANGELOG](../CHANGELOG.md); future scope belongs in
[roadmap](roadmap.md). Domain rules remain authoritative under [domains](index.md#domains).

## Current release

[Hermes 1.1.0](https://github.com/Gollardo/Hermes/releases/tag/v1.1.0) was published
on 2026-09-09 at commit `0c9c5c9` with annotated tag `v1.1.0`. It follows the
first public release, `1.0.0`, published on 2026-08-28. Distribution is tagged
source built with Docker Compose; no registry image is published.

The product is a single-owner modular monolith supported in a protected
environment. Direct public-internet exposure and multi-user hosting are unsupported.
Publication did not deploy the owner server. Operational hardening remains
explicitly deferred; the Oracle `2.0.0` vertical slice is implemented but unreleased.
Owner acceptance and a separate release decision remain before publication.

## Implemented capabilities

| Area | Current behavior | Authoritative documentation |
| --- | --- | --- |
| Access | Atomic first setup, master password, revocable sessions, idle expiry, CSRF and throttling | [Authentication](domains/authentication.md) |
| Settings | Locked base currency, timezone, default account and allocation mode | [Settings](domains/settings.md) |
| Accounts and categories | Ledger-derived balances, typed category trees, historical archived references | [Accounts](domains/accounts.md), [categories](domains/categories.md) |
| Operations | Exact income, expense, transfer and adjustment; atomic edits, version conflicts, journal pagination and reviewed occurrence confirmation | [Operations](domains/operations.md) |
| Funds | Virtual allocations, targets, manual/dynamic percentages, per-account coverage and reserve | [Funds](domains/funds.md) |
| Plans | Recurring rules and one-off plans, postpone/cancel/confirm lifecycle, series shifts and compact calendar | [Scheduling](domains/scheduling.md) |
| Forecast | Read-only exact free/total projections, fund effects, risks and event explanations | [Forecasting](domains/forecasting.md) |
| Oracle | Unreleased composed/saved alternatives, ordinary-spending envelopes, stress, exact search and account/fund feasibility | [Scenarios](domains/scenarios.md) |
| Reports | Posted income/expense totals, category breakdown and source operations | [Reports](domains/reports.md) |
| Statement import | Unreleased CSV/XLSX review, profiles, exact posting, duplicate/plan suggestions and explicit fact dates | [Import/export](domains/import-export.md) |
| Portability | Schema-1 JSON and protected Hermes V1 backup, validated atomic restore | [Import/export](domains/import-export.md) |
| Languages | RU/EN interface, browser-local preference, independent fresh category-template language | [Internationalization](ui-ux/internationalization.md) |

Language selection does not change currency, financial precision, stored names,
application dates or submitted domain values. The shared [UI contract](../DESIGN.md)
retains exact two-place financial presentation and comma/dot numeric input.
README images use synthetic English/USD data, never the owner's backup.

## Release verification

For `1.1.0`: 109 backend tests, 70 PostgreSQL 17 integration tests and 171 frontend
tests passed. The default backend run skipped 69 PostgreSQL-gated tests before
the dedicated integration pass. Lint, formatting, catalog checks, mypy,
TypeScript, documentation checks and production Compose build passed.
The final image started independently, returned health `ok`, reported `1.1.0`
and passed `alembic check` at head `0014_one_off_plans`. No migration was added.
The first integration attempt exhausted the Docker disk; the full rerun used a
disposable PostgreSQL data directory in tmpfs and passed.

The [real-backup acceptance record](operations/multilingual-acceptance-2026-09-09.md)
covers restored financial workflows, exact export equality and the four resolved
RU/EN findings. Calendar follow-up verified all seven columns at 1440 px and
internal-only scrolling at 390 px in both languages. Browser checks do not
constitute exhaustive Safari/VoiceOver certification. Historical test counts and
transient build failures from superseded development snapshots are omitted.

## Unreleased import presentation refinement

The statement-import screen now groups primary setup separately from disclosed
format settings, uses shared visual treatments, and presents compact completed
rows with source details below financial context. Empty selection and invalid
row states are explicit. Domain handlers, APIs, parsing, financial arithmetic,
and migration files are unchanged. See [screen direction](ui-ux/screens/imports.md).

Verification on 2026-09-11: `make setup`, `make lint`, `make typecheck`,
`make test` (123 default backend tests, 79 PostgreSQL integration tests and 178
frontend tests) and the production frontend build passed. The default backend
pass skipped 78 PostgreSQL-gated tests before the dedicated integration run.
Build budget warnings remain for the initial bundle and unrelated stylesheets.

The owner-provided JSON backup was restored through the existing setup API into
an isolated temporary local PostgreSQL 15 cluster. Native FastAPI and Angular
servers were used after development Compose image downloads did not complete;
this run does not verify the PostgreSQL 17 Compose image. In-app browser checks
covered the provided XLSX (five completed rows and one unrecognized trailing
row), format disclosure, source disclosure, empty selection, and 390 px reflow
without page overflow. A synthetic CSV exercised editable operation fields and
an exact negative account effect without posting. No production data or service
was changed, and private fixtures/screenshots are outside the repository.

## Release assumptions and technical debt

- At the latest successful audit on 2026-08-20, build-only `nanoid 3.3.17` had
  two high-severity findings for one advisory while the runtime production graph
  was clean. This is historical evidence, not a current audit result; re-audit the
  locked dependency graph before changing overrides.
- Style-budget warnings remain for `funds.css`, `forecast.css`,
  `forecast-chart.css`, shared `directory.css`, and `app.css`.
- Session lifetime, password policy, and throttle are documented defaults,
  not approved long-term policy.
- Password recovery is absent; losing the master password must not reopen normal
  setup.
- There is no remember-me or background expired-session cleanup. Absolute and
  idle cleanup occurs on next successful login, while guards reject expired
  sessions before deletion.
- Throttle is instance-wide rather than per-IP. This is reliable behind an
  unknown proxy but permits local denial of service through repeated failures.
- Currency validation checks an ISO-4217-style shape without an external
  registry. Currency-specific scale and exchange rates are undesigned; funds
  use shared scale 4.
- `NUMERIC(20,4)` is the current envelope, not an approved currency-specific
  precision/rounding policy.
- Account list performs one aggregate balance query per account; many accounts
  will require a batch read model.
- Journal responses may resolve names through per-operation queries; larger
  volumes require a batch read model.
- Fund summary and combined history use several aggregate queries and Python-
  side pagination; measured growth will require a read projection.
- The current model supports one fund per expense/transfer and allocation on one account;
  automatic income allocation is intentionally absent.
- Negative balance is forbidden for every current account type. Account-
  specific overdraft needs a separate future model and UI.
- One advisory lock intentionally serializes rare mutations of the entire
  category tree. Proven high write concurrency may require narrower locking.
- HTTPS reverse-proxy configurations and CSP have no external security audit.
- Frontend lock temporarily pins MCP SDK, `hono`, and `nanoid` through Angular
  build-tool overrides. An old pin is not automatically safe; review overrides
  with a network audit and Angular toolchain update.
- Materialization runs from Calendar or explicit API; no background worker is
  intentional. If Calendar stays closed, the new far edge of the one-year
  window appears at next run while existing overdue occurrences remain.
- Rule and occurrence responses may resolve names through individual queries;
  many daily rules will require a batch Calendar read model.
- Archiving an account or category does not disable a rule automatically.
  Confirmation returns a clear invalid-reference error; automatic lifecycle
  policy is deferred.
- Schedule timezone migration is absent. Timezone change is rejected after the
  first rule; an explicit migration flow is deferred.
- Series shifting now narrows row locks, but still counts all later occurrences
  and reads existing scheduled identities before filling the shifted horizon.
  Very large daily schedules may eventually need a dedicated aggregate or
  persisted materialization boundary; correctness must remain exact.
- Annual forecast returns every explaining event and holds shared locks on
  selected occurrences/accounts for the request. Measured growth may require a
  consistent read projection, but explanations must never be silently truncated.

## Scope boundaries

The [roadmap](roadmap.md) tracks unimplemented capabilities and deferred work.
Current exclusions include Oracle plan-draft conversion, AI and probabilistic prediction,
debts, budgeting, multi-currency, multi-user access and background workers.
Implemented domain documentation records narrower limits such as recurrence
ranges, account overdraft policy and one-fund-per-operation support.

## Next action

For deployment, validate a protected backup before upgrading to `v1.1.0`, then
verify health and primary financial screens using the [release runbook](operations/release.md).
For Oracle, review the implemented scenarios against a disposable restored backup,
then make a separate `2.0.0` release decision. Do not assume this task deployed production.

## Unreleased statement-import slice

The owner authorized implementation on 2026-09-10, ahead of the former roadmap
sequence. All source statuses are reviewed; the owner selects fact dates.
Migration `0015_statement_imports` adds profiles and durable receipts. No
production deployment or release publication has occurred. Raw files are not
persisted. See [ADR 0005](decisions/0005-statement-import.md) and the
[screen contract](ui-ux/screens/imports.md). Verification: 123 tests passed in the default backend run (78 PostgreSQL-gated
tests skipped there), all 79 PostgreSQL integration tests passed on a disposable
PostgreSQL 17 instance, and all 176 frontend tests passed. The focused import
suite passed again after the final authorization/downgrade assertions: 14 parser
tests and 9 integration tests. Lint, formatting, catalog checks, mypy, TypeScript,
documentation checks and production image build passed. The image returned
health `ok`, served `/imports` with HTTP 200 and passed `alembic check` at
`0015_statement_imports`. Browser acceptance exercised the provided XLSX,
all-status review, a suggested plan, explicit fact date, posting, journal link
and a 390 px layout without horizontal overflow. See the
[acceptance record](operations/statement-import-acceptance-2026-09-10.md).

Next action: owner review of a small statement against a restored backup before
any production migration. Current limitations include synchronous bounded
processing, browser-memory drafts, manual overlap reconciliation and no pending
bank reservation model. The production build warns about the initial bundle (527.64 kB against a
500 kB warning budget) and inherited stylesheet budgets. Imports reuses the
account/directory styles. No runtime infrastructure or dependency was added.


## Unreleased Oracle decision workspaces

The first deterministic slice was verified on 2026-09-11; its historical checks
remain in [the original acceptance record](operations/oracle-acceptance-2026-09-11.md).
The owner authorized the broader decision-workspace scope on 2026-09-13.

Implemented: multiple typed and recurring decisions, one/following source edits
and exclusions, up to five independent alternatives, explicit saved inputs and
backup support, manual/history ordinary-spending envelopes, reviewed exclusions,
rolling MAE, manual expense/income stress, account/fund/scope constraints and
bounded amount/date search. Missing annual recurrence dates are completed purely
in memory. Baseline and alternatives share one read-only repeatable-read snapshot;
no calculation writes facts or plans. See [ADR 0007](decisions/0007-oracle-decision-workspaces.md).

Migration `0017_saved_scenarios` adds independent versioned JSONB hypothesis
metadata and its constraints. Upgrade/downgrade preserves financial rows;
downgrade removes saved inputs. Older schema-1 backups restore with an empty
saved collection. New exports require a compatible reader. Published migrations
are unchanged; release metadata remains `1.1.0`.

Verification is maintained in the
[workspace acceptance record](operations/oracle-workspace-acceptance-2026-09-13.md).
Lint, formatting, catalog checks, mypy, TypeScript, Markdown checks and the
frontend production build passed. A fresh Compose build timed out resolving its
Docker Registry syntax image; a cached-runtime image with current code/static
assets passed health, `/oracle` and Alembic drift checks at 0017. Repeat a clean
registry-based build before release. The initial bundle is 570.05 kB against
the 500 kB warning budget; inherited style-budget warnings remain.

The full test run passed 179 default backend tests (95 PostgreSQL-gated skips),
96 PostgreSQL 17 integration tests and 197 frontend tests. The backup regression
now selects the restored occurrence by ID: a shifted series can introduce an
earlier actionable date, so list position was not stable identity.

The estimator is deliberately simple and does not certify history completeness.
Three completed training months, six displayed historical months and bounded
manual stress are engineering defaults. Missing records, seasonality and partial
categories can mislead; daily allocation is uniform by assumption. No probability
or guaranteed future balance is claimed. Daily feasibility does not validate
intraday execution order. Unsaved edits remain browser-memory only.

Measured local detached calculation with 1,000 source events, 5 alternatives,
50 changes each, 1 annual envelope and 2 accounts: 0.305 seconds to compare,
1.468 seconds/33 evaluations for amount search, and 15.118 seconds/366 evaluations
for a full-year date search without a solution. The detailed comparison serialized
to 10.63 MB; explanation duplication and bounded synchronous searches are known
performance debt. These are synthetic measurements, not latency guarantees or
maximum-capacity certification. No external infrastructure/dependency was added.

Next: review representative owner decisions and ordinary-spending categories on a
disposable restored backup; assess estimate quality and acceptable response sizes,
then make a separate release decision. No production deployment occurred.
