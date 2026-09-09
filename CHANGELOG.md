# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project intends to follow [Semantic Versioning](https://semver.org/).

Entries through `0.4.6` describe internal development milestones. They were not
published as GitHub Releases or public git tags. After the first public release,
ongoing changes belong under `Unreleased` until a release version and date are
assigned.

## [Unreleased]

### Added

- Runtime Russian/English interface selection on setup, login and Settings,
  persisted per browser with Russian fallback and no reload.
- Shared catalogs for screens, validation, API errors, dates, charts and accessible
  labels, plus translation contributor guidance and completeness checks.
- Independently selected Russian/English first-run category templates; existing
  clients default to Russian and existing/restored names remain unchanged.

### Changed

- Request validation preserves HTTP 422 field/type metadata without reflecting
  input values or exception context. Localized restore confirmation maps to the
  unchanged server command.
- Existing notices retranslate on language changes; financial formatting,
  exact payloads, currency/timezone rules and backup schema remain unchanged.

### Fixed

- Restore button, prompt and submission guard now share the currently selected
  language's confirmation phrase while preserving the published API command.
- Rejected operation submissions show an alert inside the active composer and
  retain the entered data for correction and retry.
- Calendar series shifts use signed day plurals in Russian and English; Russian
  backup summaries use count labels without incorrect noun inflections.
- Forecast date ticks adapt to chart width and keep edge labels inside the plot.

### Migration

- None. Interface language is browser-local and template language affects only
  names created during atomic setup. Existing migration head remains
  `0014_one_off_plans`.

## [1.0.0] - 2026-08-28

### Added

- One-off income, expense and transfer plans backed by Scheduling occurrences,
  with Calendar origin labels, edit/cancel actions, forecast participation,
  transactional application and a durable link to the posted operation.
- Migration `0014_one_off_plans`, backup validation for one-off origin, and the
  server-provided application-today value consumed by the operation composer.

- Versioned `.hermes` backup envelopes with Argon2id-derived KEKs, random
  256-bit DEKs and independent XChaCha20-Poly1305-IETF operations for the DEK
  and financial payload.
- Protected export and restore flows with separate backup and destination
  password roles, strict pre-Argon KDF/size validation and generic
  authentication-failure messages.

### Changed

- Future dates submitted to the public Operations API now return
  `future_operation_requires_plan` instead of creating a future journal fact.

- Settings now offers both the recommended protected `.hermes` download and an
  explicit plaintext JSON download. Legacy `hermes-json-backup` schema 1 remains
  importable for backward compatibility.
- The maximum outer backup request is 72 MiB so Base64 can carry the existing
  50 MiB plaintext payload limit.

### Migration

- Migration `0014_one_off_plans` follows `0013_fund_reserve`. PyNaCl 1.6.2 is
  the new locked runtime dependency.

### Fixed

- Malformed legacy JSON remains a legacy backup validation error instead of
  being mislabeled as an invalid Hermes envelope.
- Backup validation now distinguishes fund-to-fund transfers from
  redistributions between accounts, so valid schema-1 backups containing a
  `fund_transfer` event can be previewed and restored.
- Backup restore now writes parent categories before their children, regardless
  of UUID/export order, so valid category trees satisfy the immediate
  self-referencing foreign key during import.

## [0.4.6] - 2026-08-20

### Changed

- Dynamic fund percentages now weight the unfilled relative share of each
  target instead of its absolute missing amount, so equally completed goals
  receive equal shares regardless of target size. With 20 or more active goals,
  the guaranteed equal base consumes the complete percentage.
- Actual previews, transfer allocations, manual-mode snapshots and sequential
  forecast projections reuse the same exact relative-progress calculator.
- Long recurring-rule checkbox labels keep natural control sizing and align
  from the first line on narrow layouts.
- Application version advanced to 0.4.6.

### Migration

- No database revision is required: allocation percentages remain derived from
  existing balances and positive targets. `0012_recurring_series_shift` remains
  the single schema head.

## [0.4.5] - 2026-08-19

### Added

- Exact addition and subtraction expressions in operation, transfer-allocation,
  recurring-rule and occurrence-confirmation amount fields.
- Optional recurring-rule policy that shifts untouched later occurrences by the
  same number of days when the current occurrence is postponed.
- Migration `0012_recurring_series_shift` and backward-compatible backup fields
  for the rule policy, accumulated series offset and explicit protection of
  automatically cancelled dated exceptions.

### Changed

- Postpone responses report whether a series shift was applied, its day delta,
  and counts of shifted and preserved occurrences.
- Automatically cancelled occurrences preserved during a series shift expose a
  dedicated state instead of relying on an offset mismatch, and Calendar names
  that state explicitly.
- Series shifting locks only the selected occurrence and mutable later
  candidates; confirmed and manual exceptions no longer receive unnecessary row
  locks.
- Calendar and occurrence-action styles are split into separate scoped component
  files so Scheduling-owned styles stay below the component-style warning
  budget without changing its layout or interaction patterns.
- Application version advanced to 0.4.5.

- All UI monetary amounts and percentages now use spaces between thousand
  groups, a decimal comma and exactly two fractional digits with exact
  `ROUND_HALF_UP` presentation rounding.
- Amount and percentage inputs accept either comma or dot as the decimal
  separator while preserving exact decimal API payloads. Exact 100% percentage
  breakdowns use a display-only largest-remainder adjustment so visible shares
  also total `100,00%`.

## [0.4.0] - 2026-08-17

### Added

- Global manual/dynamic fund allocation mode with atomic switching.
- Target-aware dynamic percentages with a guaranteed base share and exact,
  deterministic four-decimal distribution.
- Sequential dynamic fund projection for scheduled replenishments.
- Migration `0011_dynamic_fund_allocation` and backup support for the mode.

### Changed

- Filled and archived funds are excluded from dynamic allocations; restored or
  spent funds automatically return when below target.
- Dynamic percentages are recalculated for each preview, confirmed replenishment
  and planned forecast occurrence. Target overshoot remains allowed without an
  intra-operation redistribution.
- Switching to manual mode freezes the current calculated percentages.
- Application version advanced to 0.4.0.

## [0.3.0] - 2026-08-17

### Added

- Quick-create operation menu with a preselected operation type.
- Optional active default account for new income and expense operations.
- Income/expense category report for monthly and custom periods.
- Fund-balance perspective for planned transfers with percentage allocation.
- Application-wide visual redesign with the confirmed light neutral direction.

### Changed

- Scheduled transfer allocation text now uses the full form width.
- Free-money forecasts subtract future transfer allocations while total-money
  forecasts keep transfers neutral.
- Forecast insights no longer reduce chart width; chart date labels remain
  visible, overview income charts render for a single category, and the fund
  projection uses a larger, higher-contrast structure diagram without the
  uninformative line chart.
- Operation create menus stay within the available responsive width.
- Application version advanced to 0.3.0.

## [0.1.2] - 2026-08-15

### Added

- 30-minute server-enforced inactivity expiry for authenticated sessions.
- Free-money default and explicit all-money switch for the forecast chart.
- Project favicon aligned with the Hermes visual direction.
- Versioned full JSON backup schema 1 with canonical SHA-256 integrity,
  exact-decimal settings, ledger, fund and scheduling state.
- Settings restore flow with preview, explicit replacement confirmation,
  destination-owner re-authentication and transactional invariant checks.

- Recurring income, expense and transfer rules with daily, weekly, monthly and
  yearly frequencies, inclusive date bounds and optimistic editing.
- One-calendar-year idempotent occurrence materialization with persistent
  pending, postponed, cancelled and confirmed states.
- Monthly calendar, account/type filters, upcoming and overdue list, plus quick
  confirm, postpone and cancel actions.
- Atomic occurrence confirmation through the Operations posting contract and a
  durable link to the actual financial operation.
- Migration `0006_recurring_operations`, ADR 0003 and unit/integration/frontend
  coverage for recurrence, rule synchronization, concurrency and rollback.
- Virtual fund definitions, per-account ledger positions and coverage summary.
- Exact allocation preview with manual correction and documented round-down
  remainder policy.
- Atomic fund-aware expenses/transfers, virtual redistribution and complete
  fund movement history.
- Migration `0005_virtual_funds` plus upgrade/downgrade, rollback, concurrency,
  integration and frontend coverage for the alpha.4 invariants.
- Financial posting model ADR with explicit alpha assumptions and invariants.
- Atomic income, expense, transfer and balance-adjustment CRUD.
- Filtered, paginated operation journal with details and responsive Angular UI.
- Migration `0004_financial_operations`, optimistic operation versions and
  clean/existing-database PostgreSQL coverage.
- Account creation, list, derived balance, edit, archive/restore and safe deletion.
- Exact initial balances posted as atomic `balance_adjustment` operations.
- Income and expense category trees with subcategories, editing and archival.
- Authenticated Angular screens for accounts and categories.
- Migration `0003_accounts_categories` and PostgreSQL/unit/frontend coverage.

### Changed

- Read-only dates use the Russian textual format, known currencies use symbols,
  and normalized decimal inputs retain spaced thousands grouping.
- JSON restore now validates complete operation shapes, category trees,
  scheduling links, physical coverage and per-fund positions before replacement;
  re-authentication uses the shared throttle and successful restore revokes
  other sessions.
- Backup uploads are capped at 50 MiB before JSON parsing, destructive restore
  requires the exact confirmation phrase, and the settings screen shows the
  full preview summary and verified export time.
- Development-only `hono` and `nanoid` transitive dependencies were pinned to
  patched compatible versions; `npm audit` reports no known advisories.
- Alembic now commits each historical revision separately so clean upgrades can
  safely use PostgreSQL enum values introduced by an earlier revision.

- Calendar month reads now consume every bounded API page, while the limited
  upcoming list exposes its complete result count.
- Confirmed calendar items open their exact posted operation; narrow layouts
  show the action list first and keep all current navigation destinations visible.
- Scheduling and Operations now use explicit public posting/ledger contracts,
  deterministic concurrent lock ordering and constraint-specific delete errors.
- Common exact-money validation moved to `app.core` so Accounts, Operations,
  Funds and Scheduling share one no-float input contract.
- Account deletion and category type changes now preserve recurring-rule and
  expected-occurrence references.
- Posted operations linked to confirmed expected occurrences cannot be deleted
  independently.
- Account balances now include all ordinary journal movements; the conservative
  alpha policy rejects mutations that would leave an affected account negative.
- Base currency now locks on the first account write; categories remain currency-independent.
- Financial JSON values use decimal strings and reject binary floating-point input.
- Balance correction now accepts the expected balance in the UI and posts an
  exact calculated ledger delta with current/difference preview.
- Calendar defaults and migration use the configured application timezone.
- Historical category types and concurrent account deletion are protected by
  operation-aware lifecycle checks and shared locking conventions.
- Journal rows show transfer direction, retain existing archived references and
  preserve visible rows while another page loads.

## [0.1.0-alpha.1] - 2026-08-02

### Added

- One-time first-run setup for master password, base currency and timezone.
- Argon2id owner credential, persistent login throttling and revocable server-side sessions.
- HttpOnly session cookies plus double-submit CSRF protection for state-changing requests.
- Authenticated settings UI for preferences, password changes and session termination.
- Initial access/settings schema plus an initialized-data hardening migration.
- PostgreSQL integration coverage for migration, session expiry and concurrent
  throttle/currency-lock invariants.

### Security

- Production-like Compose binds to loopback until the owner deliberately exposes
  an initialized instance.
- Successful authenticated responses and cookies are sent only after database
  commit; currency locking is serialized against concurrent settings updates.
