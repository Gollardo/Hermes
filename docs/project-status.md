# Project status

Last reviewed: 2026-09-27. This is the current release snapshot, not a task log.
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
explicitly deferred; the next product milestone is Oracle `2.0.0`, whose detailed
design still requires approval.

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
| Reports | Posted income/expense totals, category breakdown and source operations | [Reports](domains/reports.md) |
| Statement import | Unreleased CSV/XLSX review, profiles, exact posting, duplicate/plan suggestions and explicit fact dates | [Import/export](domains/import-export.md) |
| Portability | Schema-1 JSON and protected Hermes V1 backup, validated atomic restore | [Import/export](domains/import-export.md) |
| Languages | RU/EN interface, browser-local preference, independent fresh category-template language | [Internationalization](ui-ux/internationalization.md) |

Language selection does not change currency, financial precision, stored names,
application dates or submitted domain values. The shared [UI contract](../DESIGN.md)
retains exact two-place financial presentation and comma/dot numeric input.
README images use synthetic English/USD data, never the owner's backup.
All five README screenshots were refreshed on 2026-09-27 from the current
production frontend build and an isolated local database. Desktop and mobile
captures were visually inspected; browser checks verified English/USD content,
no horizontal document overflow and no JavaScript page errors. Capture details
are recorded in the [screenshot notes](assets/readme/README.md).

## Unreleased UI refresh

The owner authorized the whole-application redesign on 2026-09-26. The
[personal financial atlas](ui-ux/atlas-refresh.md) now defines the implemented
shell, financial hierarchy, typography, surfaces, bars, responsive layouts and
shared controls. Existing light neutral/green identity, financial calculations,
API contracts and operation workflows are preserved. This implementation is
available locally; owner visual acceptance and deployment are still pending.

Verification: 177 default backend tests passed (113 PostgreSQL-gated tests
skipped), 114 integration tests passed on isolated PostgreSQL 15, and 186
frontend tests passed. Lint, formatting, catalog checks, mypy, TypeScript and
production build passed. Build warnings remain for the initial bundle and some
component style budgets; budgets were not raised. PostgreSQL 17 acceptance was
not repeated for this presentation-only change.

Browser checks covered the nine main destinations and statement import at
390px, plus desktop layouts and the operation composer without saving. No
horizontal page overflow remained in the checked narrow layouts. First setup,
login, restore and every empty/error state were not individually captured;
shared styles apply there and existing automated scenarios remain in place.

## UI review corrections

The follow-up owner-authorized review corrections address all eleven findings:
compact mobile navigation, earlier forecast plot, explicit bar semantics, readable
empty filter scope, larger breakdown text and whole-row links, compact overview
surfaces, consistent directory actions, reduced account explanations, consistent
selected controls and a keyboard skip link. Backend and financial contracts are
unchanged. Verification: the 188-test frontend suite, lint, formatting, catalog checks,
TypeScript, mypy and production build pass. Build size warnings remain; limits
were not increased. Browser checks cover desktop and 390 px layouts, mobile
menu keyboard navigation, skip-link focus and mobile period selection. At 390 px
the collapsed navigation measures 56 px versus 373 px previously, and the plot
begins around 1135 px versus 1940 px with the populated overdue state. No
horizontal document overflow was observed on the checked routes. Backend tests
were not repeated because this follow-up changes only presentation and client UI.

## Interaction motion

The owner-authorized [motion pass](ui-ux/motion.md) adds shared 240 ms dialog,
180 ms popover/More-menu and 120 ms press/disclosure feedback. Keyboard use is
instant; reduced motion removes scaling and retains opacity. Exits are inert,
interruptible and cleaned up before a fast reopen. No financial data or page
navigation animates, and no dependency was added. Verification: 193 frontend tests pass, alongside lint, formatting, catalog
checks, TypeScript, mypy and production build. Existing bundle/style budget
warnings remain; limits were not increased. Browser checks confirm pointer and
keyboard menu behavior, inert modal exits and removal, account composer, native
More-menu transitions and entity-list origin. No records were saved. Reduced
motion and interruption paths are unit-tested; real-device feel-check remains
owner acceptance. Backend suites were not repeated for this presentation-only
change.

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
Current exclusions include Oracle scenarios/AI, debts, budgeting, multi-currency, multi-user access and background workers.
Implemented domain documentation records narrower limits such as recurrence
ranges, account overdraft policy and one-fund-per-operation support.

## Next action

The 2026-09-23 free-money forecast correction now includes projected dynamic
reserve movements as well as fund allocations. This preserves total-money
transfer neutrality and excludes reserved excess from destination and combined
free money, including after all goals fill or when no active funds exist.
RU/EN forecast copy distinguishes manual remainders from dynamic reserves and
explicitly limits the available-to-spend figure to known plans. Historical
unplanned spending is not extrapolated. No migration or public API shape change
is required.

Verification: `make test` passed 177 default backend tests (113 PostgreSQL-gated
skips), all 114 dedicated PostgreSQL integration tests and 186 frontend tests.
The focused forecast suites passed 39 unit tests, six integration tests and
26 frontend tests. New regressions reproduce the missing reserve before the
fix and cover partial/full capacity, no active funds, exact decimals, existing
reservations, account scopes, total-mode neutrality, read-only queries and
forecast-to-confirmation equality. Lint, formatting, RU/EN catalog checks,
mypy, TypeScript, documentation checks and the production frontend build passed.

All 30 scope/mode/horizon combinations were reconciled against the previously
restored private backup in isolated local PostgreSQL 15. Browser acceptance
verified the corrected annual free balance and expanded explanation; the
390 px viewport had no horizontal document overflow. RU/EN copy is covered by
component tests. Private data and diagnostic artifacts remain outside Git.
This is local acceptance, not production deployment or PostgreSQL 17/container
certification. Existing build-budget warnings remain (534.53 kB initial bundle
against 500 kB, plus component stylesheets). No dependency was added.


For deployment, validate a protected backup before upgrading to `v1.1.0`, then
verify health and primary financial screens using the [release runbook](operations/release.md).
For product development, agree the bounded `2.0.0` scenario design before coding.

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

## Unreleased fund release slice

The owner authorized the complete release-to-free vertical slice on 2026-09-17.
Funds can release a position on the same account or atomically transfer it into
another account's free money without duplicating a purchase expense. Migration
`0016_fund_release` adds the event type. Same-account facts are immutable; linked
transfers support atomic deletion and reject ordinary editing. Dynamic reserve
refill, unchanged-request replay and backup/restore are supported.

Scope excludes purchase matching, purchase-level reimbursement limits, planning,
multi-fund splits and bank execution. No release publication or deployment is
implied. Verification: the complete backend suite passed 228 tests with PostgreSQL 17
integration enabled. After the final reversal safeguard and one additional
regression case, the affected Funds, Operations and release integration suites
passed all 43 tests. All 180 frontend tests passed. Ruff, formatting, frontend
lint, RU/EN catalogs, mypy, TypeScript, documentation links and `git diff --check`
passed. The migration was checked with Alembic metadata comparison, a populated
0015 upgrade/downgrade cycle, and refusal to downgrade after release facts exist.
Backup/restore and request replay after restore passed for both release forms.

The production frontend build passed with budget warnings (531.89 kB initial
bundle versus a 500 kB warning budget, plus component stylesheet warnings).
Browser acceptance on synthetic data confirmed comma input with four-place
precision, a cross-account release into free money, history linkage and a 390 px
layout without horizontal document overflow. The final desktop modal was also
visually inspected. Production Docker build could not resolve the Dockerfile
frontend image from Docker Hub before a network deadline; image verification
therefore remains open. No dependency or external infrastructure was added.

Next action: repeat the container build when registry access is available, then
review both release forms against an isolated restored owner backup before any
production migration. Retain a pre-upgrade backup for rollback.

## Unreleased confirmation dates and plan-row groups

The 2026-09-23 owner request extends confirmation with a reviewed non-future
fact date. Calendar and the existing composer default overdue payments to their
due date; the journal retains Apply today and adds date selection. API requests
without a date preserve their prior defaults. Explicit retries with a changed
date conflict instead of altering an already confirmed fact.

Statement review can explicitly merge compatible income/expense rows of one
plan into one exact operation on one selected date. Every source row retains
its receipt; group membership and reviewed fields are bound into its retry
hash. Posting, funds, plan closure and all receipts remain one transaction.
No migration, dependency or backup schema change is required. Transfers,
existing-fact merging, different dates, partial settlement and appending to
closed plans remain outside this slice. The unrelated forecast reserve defect
above remains outside this change.

Verification: full `make test` passed (153 default backend tests, 110
PostgreSQL-gated skips there, 111 PostgreSQL integration tests on an isolated
PostgreSQL 15 cluster, and 184 frontend tests). `make lint`, `make typecheck`,
documentation checks and the production frontend build passed. Existing bundle
and stylesheet budget warnings remain; the initial bundle is 533.72 kB.
A final focused journal rerun passed all 24 tests after preserving the
server-date semantics of the Apply today shortcut. Docker daemon was unavailable,
so PostgreSQL 17/container acceptance remains open.
Browser acceptance on synthetic data verified a past-dated one-off payment,
explicit merge consent, three purchases becoming one 1,050.00 RUB operation,
all three source links resolving to it, and the 390 px review without horizontal
overflow. This does not certify PostgreSQL 17/container deployment or exhaustive
browser/accessibility coverage. No production data or service was changed.

Next action: review this bounded flow against an isolated restored backup and
run production-like PostgreSQL 17/container acceptance before a release or
server deployment. Existing unrelated status notes above are preserved.
