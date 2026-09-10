# Roadmap

This document describes the proposed development sequence and the boundaries of
future releases.

The roadmap is not a fixed calendar plan. The scope and order of milestones may
change as the project gains experience from real-world use.

The current implementation state is documented in
[project-status.md](./project-status.md). The engineering documentation map is
in [index.md](./index.md). The actual version history is in
[CHANGELOG.md](../CHANGELOG.md): the roadmap must not assign an already-used
version number to a new future scope.

The `0.x` versions were internal development milestones. Version `1.0.0`
started the public release process on 2026-08-28.

## Development principles

The project evolves through vertical user scenarios.

Whenever possible, each completed scenario should include:

- database migrations;
- backend;
- frontend;
- validation;
- error handling;
- automated tests;
- engineering documentation updates;
- production build verification.

New functionality should not exist only at the database or API level without a
way to verify its primary user scenario.

Project priorities:

1. Correctness of the financial model.
2. Data safety and portability.
3. Simplicity of daily operation entry.
4. Simplicity of self-hosted deployment.
5. Interface usability.
6. Expansion of analytics and integrations.

## Item statuses

- `[ ]` — not started.
- `[~]` — in progress or partially implemented.
- `[x]` — implemented and passed the required checks.
- `[?]` — requires a product or architectural decision.

---

# Delivered baseline through 1.1.0

- `1.0.0` (2026-08-28): self-hosted single-owner access, exact ledger, accounts,
  categories, virtual funds, recurring/one-off plans, forecast, reports and backup.
- `1.1.0` (2026-09-09): RU/EN runtime interface and setup templates, reviewed
  occurrence confirmation, localization fixes and responsive calendar refinement.

See [CHANGELOG](../CHANGELOG.md) for release history and [project status](project-status.md)
for checks and limits. Delivered features are not future work. Operational
hardening is still deferred below; publication does not close its remaining items.

# Product plan after 1.1.0

Future milestones are product hypotheses, not approved detailed designs or a
calendar commitment. Confirm each scope separately and move unfinished work
explicitly. Deterministic scenarios precede their optional AI input; imported
facts precede history-informed analytics; multi-currency precedes investments.
The hosted platform remains a separate architectural program.

## 2.0.0 — Oracle: deterministic What if? mode

- [ ] Create a temporary purchase, income, amount-change, or date-shift scenario
  without changing the ledger or confirmed plan.
- [ ] Provide an ordinary structured form that does not depend on AI.
- [ ] Calculate baseline and alternative forecasts from one snapshot, scope,
  and horizon.
- [ ] Answer “what changes” before showing a chart: delta in free money,
  minimum, date, stress window, and affected funds or events.
- [ ] Support a user-defined stop-loss and a separate, explainable risk boundary
  suggested by the system.
- [ ] Expose assumptions and sources, and distinguish facts, plans, scenarios,
  and estimates.
- [ ] Discard a scenario by default; saving it or creating a plan draft are
  separate explicit actions.
- [ ] Cover scenario calculation with exact-decimal, snapshot-consistency, and
  no-side-effect tests.

## 2.1.0 — save and compare scenarios

- [ ] Named scenarios that do not become confirmed plans.
- [ ] Compare several amount, date, or decision-set alternatives.
- [ ] Detect a stale baseline and recalculate explicitly from new facts.
- [ ] Transfer reviewed fields only into the plan-draft composer.
- [ ] Define a backup/restore policy for saved scenarios without conversation
  history.

## 2.2.0 — local conversational input for Oracle

- [ ] An optional local-model adapter converts text into a structured scenario
  draft.
- [ ] Unknown material parameters trigger a short clarification instead of a
  hidden default.
- [ ] The user reviews the recognized amount, date, scope, and action before
  calculation or saving.
- [ ] The model explains the completed deterministic result but does not
  calculate authoritative balances.
- [ ] Chat does not create operations or plans directly, and conversations are
  not stored by default.
- [ ] Provide a complete non-AI fallback and deletion of local model artifacts.

## 3.0.0 — receivable and payable debts

- [ ] Directions `owed_to_me` and `i_owe`, counterparty, dates, description,
  and status.
- [ ] Initial amount and current balance derived from loans, receipts, and
  repayments without allowing drift.
- [ ] Partial repayment and adjustment through an explicit financial fact.
- [ ] Atomic relationship between the debt lifecycle and physical operations.
- [ ] Due date, overdue state, calendar, baseline forecast, Oracle, and reports.
- [ ] Backup/restore and migration compatibility.

## 3.1.0 — loans and installment plans

- [ ] Creditor, initial and current amounts, start date, and expected end date.
- [ ] Regular payment, frequency, and next payment date.
- [ ] A simplified user-facing schedule that does not attempt to reproduce bank
  mathematics for interest, fees, and early repayment.
- [ ] Confirming a payment atomically creates a financial operation and reduces
  the outstanding liability.
- [ ] Partial, missed, and modified payments have explicit states.
- [ ] Calendar, forecast, scenarios, dashboard, reports, and backup/restore.

Loans do not belong in the first debt release merely because both use the word
“liability”: loans have a different lifecycle, a recurring payment, and a
creditor.

## Universal bank-statement import — implemented slice, release number unassigned

The owner requested this bounded slice on 2026-09-10 ahead of the original
sequence. This does not claim a published 4.0.0 release. See
[ADR 0005](decisions/0005-statement-import.md) for the accepted all-status and
user-selected fact-date scope. Bank date detection is no longer required.

“Universal” means a shared configurable pipeline, not a promise to understand
every bank file automatically without configuration.

- [x] CSV with configurable encoding, delimiter and numeric locale.
- [x] XLSX with worksheet selection.
- [ ] Evaluate OFX and QIF separately.
- [x] Column mapping, saved format profiles, and a write-free preview.
- [x] Account selection, normalization of operation sign and type, and category
  suggestions.
- [x] Explainable duplicate candidates and manual conflict resolution.
- [x] Explicit confirmation, atomic writes through owning modules' public
  contracts, and a result report.
- [x] Bank-specific profiles build on the shared pipeline and receive no direct
  ledger access.

- [x] User-selected fact dates, all-status review and links to planned payments.

Additional formats, ready-made bank profiles, and reconciliation improvements
may ship as `4.x` minor versions without changing import ownership.

## 5.0.0 — budgeting policy, goals, and plan versus actual

- [ ] Periodic income and expense limits by category.
- [ ] Explicit policy for carrying remaining amounts between periods.
- [ ] Plan, actual, available through period end, and explainable variances.
- [ ] Warnings that neither prohibit a legitimate operation nor change the
  ledger.
- [ ] Independence of budgets from funds: a budget plans flow over a period,
  while a fund assigns money already held.
- [ ] Budget templates, backup/restore, and reports.
- [ ] Fund target date, required savings pace, and expected completion date.
- [ ] Budgets and goals become explicit inputs to baseline and What if?
  scenarios.

## 6.0.0 — history-informed forecasting and explainable analytics

- [ ] Improved search, saved filters, and bulk categorization.
- [ ] Trends in balances, expenses, income, funds, debts, and budget execution.
- [ ] Configurable dashboard and period comparison.
- [ ] Deterministic forecast baselines with backtesting and error metrics.
- [ ] Machine-readable local analytical read model that does not bypass domain
  owners.
- [ ] Explainable comparison of the user's plan with actual history, without
  replacing the plan automatically.
- [ ] Financial horizon, resilience runway, and stress windows with a disclosed
  methodology.

## 6.1.0 — history-informed Oracle

- [ ] Optional local execution without sending financial data to an external AI
  service.
- [ ] Category suggestions, anomaly detection, and trend explanations.
- [ ] A forecast as a probabilistic scenario beside the deterministic baseline,
  not a replacement for the exact financial model.
- [ ] Show data source, confidence, horizon, and quality from historical
  backtesting.
- [ ] No recommendation creates or changes a financial operation without
  explicit user confirmation.
- [ ] Allow the model to be disabled completely and its local artifacts deleted.
- [ ] Conversational analytics questions use grounded tools and read models,
  not unconstrained model guesses.

## 7.0.0 — multi-currency support and capital model

- [ ] Account currency and base reporting currency.
- [ ] Explicit exchange rate recorded on a financial operation.
- [ ] Rate source, date, and missing-rate policy.
- [ ] Separate representation of actual value and revaluation.
- [ ] Currency-specific precision, cross-currency transfers, reports, and
  backup.
- [ ] Basic asset, liability, and net-worth model suitable for a later
  investment scope.

## 7.1.0 — investments and advanced asset accounting

- [ ] Begin with a manual asset and liability register and net-worth
  calculation.
- [ ] Separate a cash account from an investment account, a position from an
  instrument, and a trade from a market-price change.
- [ ] Purchases, sales, fees, dividends, and realized and unrealized results.
- [ ] Manual quotes as the baseline; an external market-data provider requires
  a separate ADR, cache, provenance, and degradation policy.
- [ ] Real estate, vehicles, and other non-market assets use periodic valuations
  rather than fictitious financial operations.
- [ ] Broker import and crypto assets are considered after the base model is
  stable and are not automatically part of the first investment release.

## Deferred operational hardening after 1.0.0

Deferred by the owner on 2026-09-09 in favor of multilingual foundation. These
items remain open; relevant safety and compatibility checks still apply to each
release. Existing protected-deployment restrictions remain in force.

- [ ] Define supported PostgreSQL, Python, Node, Docker, and browser versions.
- [ ] Verify upgrades and backup/restore between public versions.
- [ ] Add automated local backups, validation, and limited rotation.
- [ ] Publish a multi-architecture image and document upgrades, rollback,
  reverse proxy, VPN, and HTTPS.
- [ ] Resolve known critical defects and complete the release/security
  checklist.

## Parallel everyday-work backlog

These improvements may be included in the nearest thematically appropriate
release if they do not dilute its acceptance criteria:

- operation templates and duplication;
- a more convenient calendar and further mobile adaptation;
- additional export formats;
- PWA and limited offline mode;
- extended backup diagnostics and password-only protected-backup rewrap.

---

# Hermes Online strategic program

A potential free online platform—with a subscription, without one, or supported
by voluntary donations—is not an ordinary continuation of the self-hosted
deployment. Before assigning it a version, the project needs a separate
feasibility milestone and an ADR covering these decisions:

- whether self-hosted Hermes remains the primary product and whether a hosted
  edition can exist without a closed functional fork;
- identity, password recovery, email verification, roles, tenant isolation,
  account deletion, and data export;
- encryption, secret management, rate limiting, abuse prevention,
  observability, incident response, vulnerability disclosure, and privacy
  policy;
- background-job isolation, per-tenant backup, disaster recovery, and restore
  verification;
- costs for PostgreSQL, files, email, model inference, and support;
- subscription, donations, or a fully free model, as well as taxes and the
  payment provider;
- AGPL licensing, contribution rules, and a transparent division between
  shared and hosted components.

Until these questions are resolved, the current guarantee remains unchanged:
one owner in a protected environment. Code for new domains must not depend
prematurely on multi-tenant or cloud infrastructure.

---

# Version and release policy

- The entire `0.x` series is for internal trial use. Versions `0.1.0`–`0.4.6`
  and subsequent numbers before a separate owner decision are not stable public
  releases.
- The first stable public release is `1.0.0`, published after the separate
  owner decision on 2026-08-28. Future publication also requires a release decision.
- Major product generations use `2.0.0`, `3.0.0`, and so on. Functional
  improvements within a generation ship as minor `N.x.0` versions, while
  compatible fixes ship as patches `N.x.y`.
- After `1.0.0`, every public major, minor, and patch receives an annotated git
  tag, a GitHub Release, a changelog entry, and any required migration and
  backup notes. A distributed container image uses the same version.
- Whenever possible, an incompatible change after `1.0.0` waits for the next
  major version and always has an explicit migration path. A minor version must
  not silently break the API, backups, or stored data.
- `N.x.0-rc.1` prereleases may verify a real upgrade; a prerelease does not
  replace a stable backup/restore test.
- Published migrations are never rewritten after the first public release.

---

# Rules for changing the roadmap

When changing the roadmap:

1. Check consistency with the architecture documentation.
2. Do not mark an item complete solely because backend code exists.
3. Move unfinished functionality between releases explicitly.
4. Do not add infrastructure without architectural justification.
5. Update [project-status.md](./project-status.md) when the current phase
   changes.
6. Do not use the roadmap as a log of every commit.
7. Do not specify calendar deadlines without an explicit owner decision.
