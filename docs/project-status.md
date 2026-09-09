# Project status

This document is the factual snapshot of implemented and verified capabilities.
The strategic sequence lives in [roadmap.md](./roadmap.md), and the documentation
map lives in [index.md](./index.md).

## Last updated

2026-09-09

## Current phase

**Version `1.0.0` is the first stable public release.** Previous version numbers
were owner development milestones and were not published as GitHub Releases or
public git tags.

On 2026-08-28, the owner accepted Hermes on a restored copy of real data and
approved publication of the first public tag. On 2026-09-09 the owner selected
`1.1.0 — multilingual foundation` as the next milestone and deferred operational
hardening. The multilingual foundation is now implemented and locally verified,
but remains unreleased. The [implementation record](multilingual-foundation-plan.md)
and [i18n contract](ui-ux/internationalization.md) describe the accepted scope.

### Multilingual verification — 2026-09-09

- Russian and English runtime catalogs cover all implemented screens, validation,
  notices and accessible labels. The browser-local preference also works before
  login; switching preserves entered data and does not issue financial writes.
- Fresh setup independently selects Russian or English category templates.
  Existing names and restored content remain unchanged. No migration is needed:
  database schema, settings and backup formats remain unchanged at head `0014_one_off_plans`.
- `make test`: 109 backend tests passed (69 PostgreSQL-gated skips in the first
  run), then all 70 PostgreSQL integration tests passed; 163 frontend tests passed.
  `make lint typecheck`, catalog/source checks and production frontend build passed.
  `alembic check` detected no schema changes. Final Docker image verification is
  blocked: two builds failed at `npm ci` with network `ECONNRESET`; a previous
  intermediate image build succeeded, but does not certify the final sources.
  The disposable test database and local verification server were stopped.
- Live browser checks used disposable PostgreSQL data: setup, login, overview,
  accounts, funds, forecast, calendar, reports and settings; mobile width 390 px,
  language selection by keyboard and accessible labels were inspected.
  This is not exhaustive Safari/VoiceOver certification.
- Both catalogs are eagerly bundled. The initial frontend bundle exceeds the
  500 kB warning budget by 15.45 kB (515.45 kB total); existing component CSS
  warnings remain.
  Native file/date dialogs can retain the browser or operating-system language.
  Cross-tab preference synchronization is outside this scope.

The owner confirmed the version policy on 2026-08-18: the `0.x` series remained
internal testing, `1.0.0` is the first stable public release, and major product
generations continue as `2.0.0`, `3.0.0`, and so on. Intermediate improvements
use minor and patch numbers. The scopes of those future generations remain
proposals. The separate Hermes Online feasibility program is outside the current
release scope.

The owner also changed the long-term north star on 2026-08-18. Hermes should
primarily answer: “What will happen if I make this financial decision now?”. The
future capability is named Oracle, and its primary scenario mode is What if?.
The direction is confirmed but not implemented in `0.4.6` and does not expand
the current release gate.

The owner confirmed the ADR 0001 no-negative-balance policy, ADR 0002 fund
rounding and archive rules, and ADR 0003 recurrence constraints for the current
release. The current single-owner product does not require a separate audit
trail.

The confirmed first-release deployment boundary is a protected environment:
loopback or a trusted network, with VPN or an HTTPS reverse proxy for remote
access. Direct public-internet exposure is unsupported.

## Product and UI/UX foundation

- `docs/ui-ux/` records the vision, UX principles, preliminary visual direction,
  information architecture, and key-screen directions.
- The owner confirmed the P0 focus: dashboard is an overview, free money is
  primary, fast operation creation remains available, and analytics answer
  questions about future balance and largest expenses.
- The first-prototype direction is light neutral premium minimalism with a muted
  green accent and Quixotic as the primary visual reference. Dark mode is
  deferred.
- The current Angular frontend follows that direction: access and setup,
  adaptive shell navigation, overview, accounts, categories, settings, system
  states, and journal use one hierarchy of surfaces and actions. Funds and
  forecast are working vertical slices.
- On 2026-08-18 the owner approved the implemented `0.4.0` interface as the
  first-public-release baseline. This does not turn current CSS values into a
  final design system or approve future screens.
- Owner feedback from 2026-08-12 is implemented as UX stabilization: the
  sidebar can be hidden with the choice preserved, entity composers open as
  modal layers, amounts use one grouped format, categories are split into
  income and expense, and Overview shows a factual summary instead of onboarding
  or release cards.
- The forecast redesign from 2026-08-15 turns the former chart into a decision-
  making screen. One forecast view model synchronizes safe to spend, minimum,
  cash gap, period end, chart, events, risks, and total flow. Desktop and mobile
  states were compared with the conceptual reference; recommendations without a
  domain model were not added.
- The fund visual refinement from 2026-08-17 separates primary monetary totals
  from secondary percentages, discloses rare transfers on request, and presents
  funds as one dense comparison list. Existing calculations, forms, and API did
  not change; desktop and mobile states were browser-verified.
- The Calendar visual refinement keeps its scheduling lifecycle and actions
  unchanged while compacting the no-attention state, preserving visible filters,
  replacing per-occurrence calendar cards with an exact signed daily net,
  presenting negative nets on a soft risk surface with a textual overdue count,
  making each populated date open the complete day dialog, and flattening the
  recurring-rule list. The internal calendar scroll and explicit day dialog remain.
- Owner feedback from 2026-08-14 added three compact circular charts to
  Overview: current-month expense and income by root category, and fund shares
  of total saved money. Categories are collapsed by default, with one parent of
  each type open at a time.
- Owner feedback from 2026-08-15 established one textual date format, currency
  symbols, a 30-minute idle timeout, and free money as the initial forecast
  chart mode.
- The owner decision from 2026-08-18 defines one numeric UI contract: every
  amount and percentage groups thousands with spaces and shows exactly two
  digits after a decimal comma (`100 000,00`, `12,50%`); fields accept comma and
  dot as equivalent decimal separators. Shared frontend utilities implement the
  contract with exact `ROUND_HALF_UP`; exact server-side 100% breakdowns close
  visually by largest remainder without changing source data.
- Version `0.4.5` lets monetary operation and scheduling fields evaluate exact
  addition/subtraction expressions on blur and before submission. Recurring
  rules may also opt into shifting untouched later occurrences when one event
  is postponed; confirmed and manually changed occurrences remain fixed.
- Version `0.4.6` weights dynamic fund allocations by each goal's relative
  unfilled share. Equal completion progress therefore produces equal dynamic
  shares regardless of target size. Long recurring-rule checkbox labels also
  keep natural control sizing and align from their first text line.
- Version `0.5.0` caps dynamic allocations at their goals, iteratively
  redistributes the remainder in one transaction, and keeps final excess in a
  separate reserve on the receiving account. Reserves from all accounts refill
  incomplete funds automatically; operation-caused refills roll back with the
  operation. Funds and forecast show reserve totals separately, while the only
  manual action returns reserve to free money on the same account.
- The current worktree adds one-off future plans on the existing Scheduling
  occurrence lifecycle. Future ordinary operations are rejected by the public
  journal API; planned income, expense and transfers remain balance-neutral
  until explicitly applied today. The local backend unit suite, full disposable
  PostgreSQL integration suite, frontend suite, lint, type checks, documentation
  check and Alembic model/schema check pass against migration `0014`.
- A busy calendar day exposes an “More” control that opens every event of that
  day in a modal. Opening an actionable recurring event starts a reviewed
  confirmation in the established operation composer, where its operation
  fields may change without editing the rule or siblings. Early confirmation
  posts the fact on the current Hermes application day, including transfers
  that allocate to funds. Confirmed snapshots remain available from their
  calendar day but no longer contribute to its planned net total. Opening an
  unconfirmed one-off event opens the one-off plan editor. The
  Operations journal shows one-off plans due on server-provided application
  today in a distinct balance-neutral attention section. Each can be edited or
  explicitly applied from the journal after a consequence confirmation; a
  successful application refreshes the actual journal. Other pending or
  postponed plans remain in a separate section, and shared filters apply where
  their meaning is available.
- The owner decision from 2026-08-18 confirms the decision-first “Oracle · What
  if?” direction. Temporary alternatives compare with a baseline, change neither
  ledger nor plan, and persist only by choice. The owner may set a stop-loss,
  while Hermes may separately suggest an explainable risk boundary. Local AI is
  an optional natural-language-to-reviewed-draft adapter; the full workflow
  works without it, chat writes no operation, and conversation is not stored by
  default.
- Income and expense require a category, use a fact date without time, support
  batch manual entry, and have no separate MVP payee. ADR 0001 records the
  posting model and current universal prohibition on negative physical balance.
  Overdraft is deferred. A separate immutable edit and deletion history is
  unnecessary in the current single-owner scope.

## Verified capabilities

### 1.0.0 verification snapshot

- On 2026-08-28, backend tests passed 107/107, frontend tests passed 131/131,
  and the full PostgreSQL integration suite passed 65/65 against isolated
  disposable PostgreSQL 17 databases. The suite covers migrations through
  `0014_one_off_plans`, backups and restores, financial atomicity, reserve
  behavior, scheduling, and concurrency boundaries.
- Ruff, Python formatting, Angular lint, Prettier, mypy, TypeScript,
  documentation checks, `git diff --check`, and the production Docker image
  build pass. Alembic reports one head at `0014_one_off_plans` and no
  ungenerated upgrade operations. Angular component-style warnings begin at
  4 KiB and remain visible; their hard build limit is 10 KiB, which accommodates
  the currently compiled 8.13 KiB style without masking future growth.

### First run and access

- A clean instance is detected through public setup status and displays an
  Angular first-run wizard.
- The first setup step offers a previous-version JSON backup or a clean start.
  For a clean start, the owner may select optional expense questions; selected
  two-level trees and five baseline income categories are created atomically
  with the owner. Every question may be skipped.
- A backup selected on first run undergoes integrity, domain, and post-write
  checks in one setup transaction after a new master password is created. On
  failure the instance remains uninitialized, and backup credentials are not
  imported.
- Production-like Compose publishes a clean instance on loopback only; the
  owner completes setup before deliberate LAN or remote exposure.
- Setup atomically creates the sole owner, Argon2id master-password hash, base
  currency, IANA timezone, login throttle, and first session.
- Repeated setup receives a conflict and cannot replace credentials or settings.
- An initialized instance without a session displays master-password login.
- The protected shell and Settings API are inaccessible without a valid server
  session.

### Authentication and sessions

- A random session identifier travels in an HttpOnly, SameSite=Lax cookie;
  PostgreSQL stores only its SHA-256 digest.
- Mutating cookie-authenticated requests also require a per-session double-
  submit CSRF token.
- Current session, logout, logout-all, and a default seven-day absolute lifetime
  are supported.
- The browser shell expires after 30 minutes without interaction. Keyboard,
  pointer movement or press, touch, and scroll extend the local deadline and
  trigger a rate-limited CSRF-protected heartbeat. The backend independently
  rejects an idle session.
- Changing the master password requires the current password and terminates
  other sessions.
- Persistent login throttling blocks login for 15 minutes by default after five
  failures in a 15-minute window.
- Public API is limited to health, setup status, two setup commands, and login;
  application routers share one authentication dependency.
- The transactional dependency completes before a successful HTTP response and
  session cookies are sent.

### Settings

- The owner may view and change timezone before the first recurrence rule.
- Base currency may change before the first account or monetary operation.
- `settings.lock_base_currency()` is the public transactional contract for
  future financial modules. After lock, currency change is forbidden.
  Scheduling separately locks timezone after the first rule.
- Currency and timezone updates and their locks serialize through a row lock on
  singleton settings, including concurrent transactions.
- Backend validates a three-letter currency code and IANA timezone independently
  of UI.
- Default account accepts only an active account and preselects it only for new
  income and expense. The choice remains editable; account archive or deletion
  clears the setting atomically.
- Fund mode switches between manual and dynamic percentages. Enabling dynamic
  mode requires targets for all non-archived funds. Returning to manual mode
  atomically preserves current calculated percentages.

### Schema and delivery

- The first public migration, `0001_first_run_access`, creates owner credential,
  sessions, login throttle, and application settings. Migration
  `0002_harden_access_invariants` adds database checks while preserving
  initialized data.
- The production image contains the Angular build and FastAPI, runs Alembic
  before Uvicorn, and exposes one HTTP entry point.
- Migration `0011_dynamic_fund_allocation` adds the global mode with safe
  `manual` backfill, a database check, and reversible downgrade to `0010`.
- Session, throttling, and Secure-cookie runtime parameters use `HERMES_*`.
  Development Compose explicitly uses a non-Secure cookie only for local HTTP.
- Alembic executes historical revisions as separate transactions: clean upgrade
  commits PostgreSQL enum additions before dependent check constraints.
- Migration `0008_session_idle_timeout` adds server-side activity timestamp and
  checks while preserving existing sessions by initializing from creation time.

### Backup and restore

- Settings provides two explicit exports: recommended protected `.hermes` V1
  and plaintext `hermes-json-backup` schema 1 for compatibility. Both preserve
  exact decimal strings and identifiers for settings, ledger, fund, and
  Scheduling data.
- Hermes V1 derives a KEK with bounded Argon2id parameters, wraps a fresh random
  256-bit DEK and authenticates the payload and wrapped key with independent
  XChaCha20-Poly1305-IETF operations. Financial data does not appear in the
  outer UTF-8 JSON envelope.
- Checksum verification preserves the canonical shape of an old schema-1
  document; later optional fields do not break import of an earlier copy.
- Preview checks format, version, authentication or legacy checksum, payload
  schema and domain references before any write and shows a summary. Unsafe KDF
  values and malformed lengths are rejected before Argon2.
- Restore requires CSRF, the destination master password, and an exact
  confirmation phrase. Exclusive locks, one transaction, and post-write checks
  prevent partial replacement.
- Encrypted restore treats the backup password separately from the current
  destination password or new first-run password. Wrong passwords and damaged
  authenticated ciphertext share one non-diagnostic UI error.
- Credential, login throttle, and sessions are not exported. Restore uses the
  shared throttle, preserves the current session, and terminates the others.

### Accounts and balances

- The owner can create, view, and edit `cash`, `debit`, and `savings` accounts,
  and archive or restore them.
- A nonzero initial balance atomically creates a `balance_adjustment` and
  movement. Current balance is the sum of `NUMERIC(20,4)` movements and is
  returned as a string.
- The API rejects `float` for money and limits alpha scale to four places.
- An account without movements may be deleted. History returns a conflict and
  requires archiving.
- The first account write locks base currency in the same transaction. Creating
  a currency-independent category leaves it editable.

### Categories

- The owner can create and edit separate income and expense trees; UI is
  optimized for category and subcategory.
- A parent must be active and have the same type; cycles are forbidden.
- API and UI support exactly two levels; a third level is rejected.
- Active children block parent archiving, and an archived parent blocks child
  restoration.
- Archived categories remain readable in history. The public validation
  contract rejects them for new operations and has an explicit historical-read
  mode.
- Category type is immutable while a financial operation references it; the
  application use case checks the Operations-owned history contract.
- Tree mutations and validation of a new operation reference serialize through
  one transaction-level advisory lock.

### Financial schema

- Migration `0003_accounts_categories` adds `accounts`, `categories`,
  `financial_operations`, `account_movements`, and PostgreSQL enum types.
- Migration `0004_financial_operations` adds common operation types, calendar
  date, category reference, adjustment reason, optimistic version, journal
  indexes, and movement uniqueness per operation/account. Old timestamps
  convert to date through application timezone; downgrade supplies a required
  legacy description for alpha.3 rows.
- Migration `0005_virtual_funds` adds fund definitions, events, virtual
  movements, source checks, foreign keys, and history indexes.
- Migration `0006_recurring_operations` adds recurrence rules, expected
  occurrences, recurrence/status enums, unique rule/date identity,
  confirmation link, and calendar indexes.
- Migration `0007_fund_targets_recurrence` adds optional fund targets,
  recurrence intervals and weekdays, and a virtual transfer type between funds.
- Migration `0008_session_idle_timeout` adds server idle timeout,
  `0009_scheduled_fund_allocation` adds planned-transfer allocation, and
  `0010_default_account` adds an optional default account.
- Migration `0011_dynamic_fund_allocation` introduced the allocation mode;
  `0013_fund_reserve` is the single current head.

### Financial operations and journal

- The owner can create, view, edit, and delete income, expense, transfer, and
  expected-balance adjustment operations. The composer calculates the exact
  signed journal delta.
- The creation button reveals four types and immediately opens the selected
  composer while keeping one entry/editing pattern.
- Income and expense require an active matching category. Transfer uses two
  different active accounts and remains one operation with two opposite
  movements.
- Creation, full movement replacement, and deletion occur in the request
  transaction. Affected accounts lock in UUID order, and version protects
  against lost update.
- The conservative alpha policy rejects a result below zero. A failed check
  stores neither a header nor half of a transfer.
- Journal filters by period, account, type, and category. It has server-side
  pagination, stable order, expandable details, transfer direction,
  full-selection net total, and localized errors.
- Account and category selection in journal, recurrence rules, funds, forecast,
  and category tree uses one searchable combobox: prefix search and up to five
  recent options for an empty query.
- The shared combobox supports keyboard and mouse. Money fields accept dot or
  comma and normalize on blur or show an error.
- The journal filter panel is collapsed by default, while active conditions
  remain visible as chips.
- Account deletion locks identity before checking history, so a concurrent post
  does not become an unhandled foreign-key error.

### Reports and fund perspective

- Reports builds income or expenses for a calendar month or custom period,
  showing a large category chart, exact totals, and grouped operations linked
  to the journal.
- Plan has a separate fund perspective with an ending-share chart and balance
  lines over the primary forecast horizon. Current active percentages apply
  only to actionable transfers with explicit `allocate_to_funds`.
- Both read models use public owner-module contracts and exact decimal
  arithmetic. Fund-perspective loading failure does not block the primary
  forecast.

### Virtual funds

- The owner can create, edit, archive, and restore funds. Active percentages
  are atomically capped at a combined 100%.
- Balances derive from the virtual journal and appear as total, by account, and
  through physical = reserved + free.
- Preview uses exact decimal arithmetic and rounds down to four places. Manual
  correction and free remainder remain visible before commit.
- An expense may consume a selected fund or remain fundless. A transfer may
  move one virtual portion; redistribution changes no physical money.
- CRUD for a fund-linked operation replaces both ledgers in one transaction and
  rechecks coverage and non-negative positions.
- History combines allocations, redistributions, expenses, and transfers.
- The screen distinguishes percentage allocation of free money, an atomic
  physical transfer followed by either percentage allocation or allocation of
  the full amount to one existing fund without changing future percentages, and
  moving an existing assignment without physical movement.
- ADR 0002 records posting model, lock order, rounding, and archive policy.
- A fund has an optional target amount with exact progress; the screen shows
  per-fund and combined progress.
- Creating a fund may atomically reserve money only for it. Moving money between
  two funds on one account preserves physical balance and total reserved.
- In dynamic mode, incomplete non-archived funds receive a guaranteed share up
  to 5% plus a portion proportional to their relative unfilled target share.
  Equal progress produces equal shares regardless of target size. At 20 or more
  active funds, the equal guaranteed base consumes the complete percentage, so
  relative progress does not differentiate their shares. Percentages and money
  close exactly to 100% and recalculate before each iterative top-up. Funds are
  capped at their goals; final excess enters the per-account reserve.
- Filled and archived funds receive 0%. Expense or restoration returns a fund
  to the next calculation when it is below target again.
- Fund perspective recalculates dynamic percentages sequentially after each
  planned top-up and reports the projected reserve instead of blocking dynamic
  events when all goals are full.

### Recurring rules and calendar

- The owner can create and edit recurring income, expense, and transfer with
  `daily`, `weekly`, `monthly`, or `yearly` frequency, start date, and optional
  inclusive end date.
- An explicit materialization command synchronizes occurrences from today
  through one calendar year. Rule lock and unique `(rule_id, scheduled_on)` make
  repeated and concurrent execution idempotent.
- Editing or disabling a rule affects only untouched current and future
  occurrences. Confirmed, postponed, manually cancelled, and overdue
  occurrences remain.
- Automatically cancelled future occurrences preserved during a series shift
  carry an explicit database-constrained marker. Their applied offset remains a
  date snapshot, and Calendar identifies the preservation state directly.
- Series postponement locks the rule, selected occurrence and only mutable later
  candidates through a partial-indexed deterministic query. Confirmed, manual
  and already protected exceptions remain outside the row-lock set while their
  count stays visible in the result.
- Confirmation creates exactly one actual operation and records the link in the
  same transaction. Postponement and cancellation create no physical movement.
- Calendar shows one month, account and type filters, and quick confirm,
  postpone, and cancel actions only for today's and overdue events.
- The month grid loads every page in the bounded range. The action list honestly
  shows the first 12 and the full selection size. A confirmed occurrence opens
  its exact operation, and mobile places the action list before the grid.
- Rule edit locks occurrences before category and account references;
  confirmation takes the same reference locks after the occurrence. The race
  serializes, and stale confirmation receives an optimistic conflict rather
  than posting an old snapshot.
- Monthly rules permit days 1–28; yearly rules reject February 29. Timezone is
  locked after the first rule, and the domain stores calendar dates without
  time.
- Weekly rules select multiple weekdays and intervals of 1–3 weeks. Monthly
  supports intervals of 1–3 months.
- A rule without end date continues rolling one-year materialization rather
  than ending after one year. Confirmed history is protected from rule edits.
- Confirmation may adjust one occurrence amount. A planned transfer may
  atomically allocate its incoming money by the active-fund percentage snapshot
  locked during confirmation; allocation failure rolls back transfer and link.
- ADR 0003 records recurrence, materialization, synchronization, and
  confirmation policies.

### Balance forecasting

- The owner can open a combined forecast or select a specific account,
  including archived, and choose two weeks, month, quarter, half-year, or year.
- Starting point derives completely from the actual ledger. Only `pending` and
  `postponed` occurrences dated from today through the inclusive horizon enter
  the future line; confirmed and cancelled are excluded.
- By default, start is current free money: one Funds batch read subtracts
  per-account reserves from the physical ledger. `total` mode restores full
  physical balance including allocated money.
- Future expense does not yet select a fund, so free mode applies it to the
  current free starting point without a hidden reserve-source assumption.
  Transfers with explicit percentage allocation appear separately in fund
  perspective.
- Events aggregate into deterministic daily closing points with exact Decimal
  amounts. Response includes period end, minimum, first possible negative date,
  and exact closing balance for that day; annual visual aggregation therefore
  does not lose the first daily cash-gap amount.
- An internal transfer has zero net effect in combined scope but remains in the
  explanation. For one account it is outgoing or incoming.
- Overdue events never shift silently; their scoped count appears separately
  with a Calendar link.
- One frontend view model derives safe to spend as `max(0, minimumBalance)`, end,
  minimum/date, first cash gap/date, income, expenses, and net flow. KPIs, chart,
  timeline, risk panel, and period summary do not recalculate them separately.
- The screen marks zero boundary, negative zone, and risk segment without color
  alone. Y axis uses rounded monetary ticks; tooltip preserves exact amount,
  change, and operation count.
- Actual starting balance participates in scale and has a separate “Now” point.
  The annual monthly chart adds an exact risk marker when a daily cash gap
  recovers before month close; the marker opens that day's operations.
- Single-account summary separately shows nonzero net transfer effect, so its
  total flow is explainable through income, expenses, and transfer flow.
- Through half-year, API and screen return daily closing points. Year aggregates
  monthly without losing source events or daily-risk precision. Every point has
  exact hover/focus tooltip; click reveals events, and timeline and risk items
  select the same date. Unapproved regression/recommendation layers are absent.
- Forecasting is a read-only module with no tables or background
  materialization; beta.2 added no migration.
- Forecast snapshot takes shared locks on expected occurrences and account
  identities in the same Scheduling → Accounts order as confirmation. A
  selected-account free forecast takes one global schedule snapshot and filters
  in memory, preserving one dynamic-top-up sequence without retaking occurrence
  locks. Concurrent confirmation therefore cannot enter both actual starting
  balance and planned part of one response.
- Before reading forecast, the screen synchronizes rolling one-year
  materialization, so the far boundary does not depend on the last Calendar
  visit. Forecast GET itself remains read-only.

## Verification snapshot

- The Unreleased encrypted-backup slice passes 101 non-PostgreSQL backend tests,
  60/60 PostgreSQL integration tests against an isolated PostgreSQL 17
  container, and 120/120 frontend tests. Dedicated coverage proves Hermes V1
  round trip, absence of known plaintext markers, fresh salts/wrapped keys and
  independent nonces, one authentication failure for wrong passwords or either
  damaged ciphertext, pre-Argon rejection of unsafe KDF parameters and unsafe
  salt/nonce/ciphertext lengths, explicit unknown-version rejection, protected
  restore into initialized and first-run targets with distinct source and
  destination passwords, rollback on failed authentication, correct legacy
  error classification, and continued plaintext JSON restore. No database
  migration is required; `0012_recurring_series_shift` remains the schema head,
  and `alembic check` reports no new upgrade operations. Ruff, Python formatting,
  Angular lint, Prettier, mypy, TypeScript, documentation checks, dependency
  consistency, the production Angular build, and the production Docker Compose
  build pass. The production npm graph reports zero vulnerabilities. The full
  development graph still reports two high-severity findings from the existing
  build-only `nanoid 3.3.17` override. Existing non-blocking Angular style-budget
  warnings also remain. The production image built successfully before the
  review hardening; two post-review rebuild attempts were blocked while resolving
  the already pinned Dockerfile frontend because Docker Hub returned `EOF`.

- For the current `0.4.6` worktree, 79 non-PostgreSQL backend tests, 59/59
  PostgreSQL integration tests and 115/115 frontend tests pass. Dedicated fund
  cases prove that equal relative completion receives equal dynamic shares even
  when targets differ by an order of magnitude, that the less complete target
  receives the larger dynamic share while a dynamic pool exists, that 21 active
  funds use only the equal guaranteed base, and that sequential forecast
  allocation uses the same calculator. Backup validation now distinguishes a
  same-account transfer between two funds from a same-fund redistribution
  between two accounts. Unit tests cover valid and malformed transfer shapes;
  the PostgreSQL backup round trip restores the two resulting fund positions,
  while category restore writes roots before children independently of UUID
  order. The owner's unchanged `0.4.6` backup passes schema, checksum and domain
  preview validation and completes first-run restore into a clean disposable
  PostgreSQL database with all 85 categories. A frontend geometry case protects
  the long series-shift checkbox from shrinking or reverting to centered label
  alignment. Alembic reports the current and only head as
  `0012_recurring_series_shift`, and `alembic check` detects no schema changes;
  release `0.4.6` therefore adds no empty migration. Ruff, Python formatting,
  Angular lint, Prettier, mypy, TypeScript, documentation checks and the
  production Angular build pass. The containerized integration coverage report
  emits source-path warnings because coverage metadata uses the host workspace
  path; test execution itself completes successfully. The browser smoke check
  reaches the local authentication screen, but the authenticated Calendar
  geometry was not manually rechecked without owner credentials. The aggregate
  host `make test` cannot connect with its default `hermes` PostgreSQL role in
  this environment; the same complete PostgreSQL suite passes inside the dev
  Compose network against disposable databases. Two production Docker Compose
  build attempts reached the locked frontend dependency install and then failed
  with npm registry `ECONNRESET`; this external network failure leaves the image
  build unverified in this pass.
- Documentation audit and subsequent numeric UI implementation on 2026-08-18
  confirmed 70 passed backend tests with 53 PostgreSQL scenarios skipped without
  opt-in, 109/109 frontend tests across 20 files, `make lint`, `make typecheck`,
  `make docs-check`, and production Angular build. `make test` requested the
  PostgreSQL scenarios, but the sandbox blocked `127.0.0.1:5432` with
  `Operation not permitted`; Docker build and browser scenarios were not rerun
  in that pass. The latest complete snapshots are below.
- For `0.4.0`, 70 non-PostgreSQL backend tests, 54/54 PostgreSQL integration
  tests, and 109/109 frontend tests passed. Dedicated cases cover 1/20/21/25
  funds, exact percentage and money closure, overshoot, recalculation after one
  fund, archive and restore, no active targets, atomic rollback, dynamic to
  manual freezing, backup round trip, and sequential forecast. Ruff, mypy,
  Angular lint, Prettier, TypeScript, docs check, production Angular build, and
  production Docker Compose build passed. Review hardening separately covers one
  global schedule snapshot for account free forecast and restoration of a
  dynamic backup whose unused manual percentages exceed 100%.
- The integration suite creates disposable databases and verifies upgrades to
  the current `0013_fund_reserve` head. A dedicated manual
  upgrade/check/downgrade cycle was not added to this pass.
- The 2026-08-20 network audit reports zero production vulnerabilities. The full
  development graph reports two high-severity findings for the same build-only
  `nanoid 3.3.17` advisory, pinned by an existing override.
- `rc.1`: 97 backend scenarios (52 non-PostgreSQL passed, 45 skipped without
  opt-in); full PostgreSQL snapshot 46/46 passed, including atomic first-run
  restore, transfer-and-allocation and rollback, and forecasting snapshot with
  the updated series contract. Frontend 63/63 passed; lint, format, typecheck,
  and docs passed.
- A historical full `npm audit` after prior overrides reported zero advisories;
  the current `0.4.6` state is described above.
- Searching backend financial code for `float` found only the input rejection
  guard and a docstring prohibiting float arithmetic.
- PostgreSQL scenarios cover clean migration and setup, protected API,
  CSRF/logout/login, password and session revocation, expiry, sequential and
  concurrent throttling, serialized currency lock, and initialized upgrade from
  `0001_first_run_access` to head; alpha.2 upgrade with an initial adjustment;
  account and category lifecycles and concurrent races; immutable historical
  category type; operation CRUD, filters and totals, conflicts, concurrent
  expense and account deletion, insufficient balance, and injected transfer
  rollback; fund lifecycle, deterministic allocation, manual remainder,
  fund-aware CRUD, redistribution, history, concurrent allocation and
  consumption, percentage-definition serialization, virtual rollback, coverage
  rollback, archive invariant, alpha.3 upgrade, and alpha.4 downgrade; timezone
  boundary, recurrence lifecycle, exact dates including a 367-day leap-year
  window, every operation type, no balance before confirmation, idempotency,
  protected manual edits, overdue preservation, concurrent materialization and
  confirmation/edit, duplicate confirmation, scheduling auth/CSRF, injected
  rollback, alpha.4 upgrade, beta.1 downgrade, full clean-target backup round
  trip, invalid-restore rollback, throttled reauthentication, other-session
  revocation, and the 50 MiB request limit. Setup separately covers selected
  category templates, duplicate-group rejection, and atomic first-run restore.
- New PostgreSQL regressions cover rollback of a fund definition when its
  initial amount is unavailable, preservation of physical/reserved totals when
  moving between funds, progress above 100%, child-category aggregation into
  root, and database checks for unique weekdays and valid recurrence intervals.
- Frontend Vitest historically covered 63 access-shell, session-expiry, setup,
  settings, health, account, category, and journal cases; timezone default,
  expected-balance adjustment, archived edit references, transfer direction,
  loading continuity, exact manual allocation preview and invalidation,
  percentage limit, physical-account fund position, monthly calendar, overdue
  state, missing-day validation, exact rule payload, quick confirmation, full
  month pagination, honest upcoming count, archived references, exact operation
  links, forecast risk and explanations, scope/horizon switches, stale loading,
  no-event state, and calendar X scale. Additional cases cover dashboard drill-
  down and partial analytics failure, exact fund progress, optional decimal
  normalization, recurrence weekdays, resettable journal filters, backup
  preview and destructive confirmation, first-run restore, password validation,
  onboarding templates, recent combobox options, emoji-prefix search, damaged
  localStorage, hidden sidebar persistence, and exact money strings.
- Beta.1 Calendar browser flow passed on desktop and mobile: all narrow-
  navigation items were visible, action list preceded the grid, statuses used
  text, the limited list showed `12 of 30`, and a confirmed occurrence opened
  the exact operation at page start.
- Ruff, Ruff format, strict mypy, ESLint, Prettier, strict TypeScript, and docs
  check pass.
- `alembic check` found no drift between model metadata and head schema;
  migration environment explicitly loads Operations, Funds, and Scheduling
  indexes and constraints.
- Production Angular build on 2026-08-18 and the previously checked production
  Docker image build pass; `npm ci` inside the image reported zero
  vulnerabilities. Angular warns that `forecast.css` 5.71 KiB, `funds.css`
  6.86 KiB, `forecast-chart.css` 5.65 KiB, `app.css` 4.89 KiB, and compiled
  `directory.css` uses of 6.86/4.35 KiB exceed the 4 KiB `anyComponentStyle`
  warning budget. Scheduling's calendar and action/rule styles are now separate
  scoped files below that budget, so its former `scheduling.css` warning is
  resolved without raising the threshold or moving selectors into global CSS.
- Production-like Compose e2e on a separate clean volume passed setup →
  authenticated shell → settings update → logout → login with no browser-console
  errors.
- Settings and backup were screenshot-audited again at 1440 px and 390 px:
  release label matched current version, no horizontal overflow existed,
  destructive flow appeared only after valid preview, and statuses had text and
  ARIA roles.
- UX stabilization from 2026-08-12 was browser-checked in production-like
  Compose: setup stayed disabled until valid passwords matched; sidebar hid and
  restored; account, operation, category, and fund composers were absent from
  baseline layout and opened as dialogs; values then rendered as `100 000.00`,
  which no longer matches the accepted `100 000,00` contract; categories split
  into income/expense; Overview showed actual totals. A `4 000.00` transfer
  between accounts at a 25% fund share atomically created `1 000.00` of new
  assignment. Annual forecast preserved layout, showed “Amount · RUB” and
  “Date” axes, and removed the former amount strip.
- Forecast redesign passed browser checks at 1440 × 1000 and 390 × 844: free/all
  changed series and safe to spend, risk/event click selected the exact date,
  body had no horizontal overflow, chart and timeline had mobile scrolling, and
  roving tabindex left one keyboard stop in forecast points. Console was clean;
  final reference comparison is `passed` in `design-qa.md`.
- The forecast composition iteration removed the left KPI column: four decision
  KPIs now sit above the workspace, with risks and totals below the full-width
  chart. Chart viewport no longer scrolls. Adaptive Y domain excludes distant
  zero for a safely positive series and restores zero line and tint near a
  shortfall. Area fill is lighter, normal markers hide until interaction, and
  tooltip is shorter.
- Free forecast treats future percentage-allocated transfers as an exact
  decrease in free money; total forecast keeps physical transfer neutrality.
  The lower chart axis is not clipped.
- Overview renders a circular chart even for one category. Fund perspective
  removed an uninformative line chart; its composition chart is larger and uses
  higher-contrast colors with an exact text legend.
- The operation-add menu is constrained to available narrow-screen width.
- The previous `0.2.0` diff passed Ruff, backend format, mypy, Angular lint,
  Prettier, TypeScript, docs check, production Angular build, 61 non-PostgreSQL
  backend tests, 96 frontend tests, and 51/51 PostgreSQL scenarios. Integration
  separately confirmed idle timeout and heartbeat, session upgrade from `0001`,
  free/total forecast with real reserves, open-ended templates, confirmation
  with amount adjustment, and atomic transfer allocation.
- The `0.3.0` corrections passed 62 non-PostgreSQL backend tests, 97 frontend
  tests, 51/51 PostgreSQL integration tests, Ruff, mypy, Angular lint, Prettier,
  TypeScript, docs check, and production Angular build. Known non-blocking style
  budget warnings remain.

## Release assumptions and technical debt

- Transfer-and-allocation records now persist the allocation event's causal
  link to their physical transfer. Deleting the transfer removes the dependent
  reservation atomically, while the ordinary operation editor rejects their
  incomplete representation. A narrowly fingerprinted compatibility path also
  handles a uniquely matched unlinked pair produced by the earlier implementation.

- At the latest successful audit on 2026-08-20, build-only `nanoid 3.3.17` had
  two high-severity findings for one advisory while the runtime production graph
  was clean. A compatible dependency update and full recheck are required
  without expanding this feature's functional diff.
- Style-budget warnings remain for `funds.css`, `forecast.css`,
  `forecast-chart.css`, shared `directory.css`, and `app.css`.
- Session lifetime, password policy, and throttle are documented alpha defaults,
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
  use documented shared alpha scale 4.
- Currency lock relies on financial modules calling the public Settings contract
  in the first monetary/account write transaction. Account creation does so
  through the application use case; category creation does not lock currency.
- `NUMERIC(20,4)` is one alpha envelope, not an approved currency-specific
  precision/rounding policy.
- Account list performs one aggregate balance query per account; many accounts
  will require a batch read model.
- Journal responses may resolve names through per-operation queries; larger
  volumes require a batch read model.
- Fund summary and combined history use several aggregate queries and Python-
  side pagination; measured growth will require a read projection.
- Alpha.4 supports one fund per expense/transfer and allocation on one account;
  automatic income allocation is intentionally absent.
- Editing replaces movements and increments version. A separate immutable
  history of previous values and deletions is intentionally unnecessary in the
  current single-owner scope. Ordinary operation description remains optional.
- Negative balance is forbidden for every current account type. Account-
  specific overdraft needs a separate future model and UI.
- One advisory lock intentionally serializes rare mutations of the entire
  category tree. Proven high write concurrency may require narrower locking.
- HTTPS reverse-proxy configurations and CSP have no external security audit.
- Legacy backup schema 1 remains plaintext with a 50 MiB limit and SHA-256
  accidental-corruption detection. Hermes V1 provides authenticated encryption
  with a 72 MiB outer limit and 50 MiB plaintext-payload limit; signatures,
  streaming and automatic rotation remain outside scope.
- Frontend lock temporarily pins MCP SDK, `hono`, and `nanoid` through Angular
  build-tool overrides. An old pin is not automatically safe; review overrides
  with a network audit and Angular toolchain update.
- Existing `0004 → 0005` upgrade and `0005 → 0004` schema downgrade were tested.
  Downgrade removes fund data, so production rollback needs a backup and
  explicit acceptance of alpha.4 ledger loss.
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

## Outside current scope

- Search, saved filters, running balance, and bulk actions.
- Account-specific overdraft, pending bank transactions, full reconciliation,
  and currency-specific precision/rounding.
- Automatic or multi-account allocation, several funds per operation, and
  target dates.
- Liabilities, debts, and their future forecast payments.
- What-if scenarios, stop-loss, system-suggested risk boundary, saved
  comparisons, and the local Oracle AI adapter.
- Recurrence intervals outside 1–3, month days 29–31, leap-day policy, drag and
  drop, notifications, and background materialization.
- CSV/Excel import, backup compatibility after payload schema 1, password
  recovery and protected-backup password rewrap UI.
- Multiple users, roles, permissions, organizations, and tenants.
- External infrastructure, Redis, broker, background workers, and cloud
  identity.

## Recommended next action

Perform owner acceptance of RU/EN workflows on an isolated restored copy, then
prepare the `1.1.0` release using the existing release checklist. Review the small
initial-bundle warning before adding further languages. Operational hardening
remains deferred; no public tag or version bump was made by this implementation.
