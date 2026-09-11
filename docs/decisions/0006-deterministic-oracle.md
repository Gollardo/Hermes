# ADR 0006: Deterministic Oracle projection boundary

- Status: accepted for the bounded implementation
- Date: 2026-09-11
- Authority: the owner requested implementation of the reviewed Oracle plan.

## Context and scope

Oracle is a deterministic planning and prediction engine over known financial
facts and plans. It must recompute downstream consequences, including sequential
fund allocations, rather than adjust an already rendered forecast line. It does
not infer unknown future spending or claim statistical prediction.

The first slice supports one exact new expense, new income, replacement amount,
or date move of one actionable occurrence. A series is not edited. Inputs span
Hermes today through the inclusive calendar-year horizon. Comparison presets
remain two weeks, month, quarter, half-year and year. An existing event may move
into or out of the selected comparison period within that annual input window.

## Decision

Scenarios owns draft validation, comparison, risk windows and explanations.
Forecasting exposes a detached `ProjectionSnapshot` and a pure `project_snapshot`
contract. Its existing exact money and Funds allocation calculators remain the
shared authority. Scenarios never calls domain mutation commands.

API composition authenticates both source reads and calculations and applies
CSRF to the POST calculation. A separate PostgreSQL `REPEATABLE READ, READ ONLY`
transaction reads settings, schedule, accounts, ledger and funds. MVCC includes
concurrent insertions as well as updates/deletions, so an occurrence cannot be
counted both as planned and actual. There are no row/advisory locks in this read
path. Authentication bookkeeping retains its ordinary separate transaction.
The snapshot is detached and both branches use its identical sources.

A SHA-256 content identity covers relevant source data and application date.
The form submits that identity and the selected occurrence version. Changed
sources return HTTP 409; the owner refreshes sources and explicitly recalculates.
The draft fields are retained. This is request-time protection, not persisted
snapshot history, a lock against later changes, or saved-scenario invalidation.

New hypothetical events use an ephemeral stable identity and explicit scenario
provenance. Replaced events retain their original identity and deterministic
`(due_on, occurrence_id)` ordering. No scenario enum is added to stored plans.
Synthetic expenses use free money and do not consume a fund. Existing planned
transfer changes rerun the entire chronological fund distribution sequence,
including transfers outside a selected account's scope. Fund results explicitly
cover all accounts; free and total cash series use the selected scope.

## Risk methodology and implementation defaults

These are bounded implementation defaults, not a permanent personal-finance
policy or an owner-approved statistical model:

- A user stop-loss is optional, nonnegative, ephemeral and denominated in the
  selected scope's base currency. It never rejects a valid financial posting.
- A stress window contains consecutive daily closings strictly below a boundary;
  equality is safe for that boundary. The actual starting point is included.
  Recovery today after an initially deficient snapshot remains visible.
- The system suggestion is `max(0, starting free balance - baseline minimum)`:
  the initial buffer covering the maximum cumulative drawdown of known planned
  flows during this horizon. With no nonzero source effects it is omitted.
- The UI discloses the formula, source period and limitations. Using that initial
  buffer as a constant warning line is conservative, not a rolling reserve
  requirement. User and system boundaries remain separate. Hiding the system
  explanation also hides its risk assessment, without changing any calculations.
- All minima and stress windows use exact daily balances before monthly chart
  aggregation. The engine uses a local decimal precision of 28 for comparison;
  financial input limits and Funds' explicit allocation rounding are unchanged.

## Source completeness

Only already materialized actionable plans are inputs. Oracle does not create
occurrences, even while opening its form. A prominent notice directs the owner
to Calendar for explicit synchronization and then to refresh sources. Existing
plans beyond the selected horizon can still be chosen within the annual window.
No historical recommendation is manufactured when known plans are sparse.

## Persistence, migration and alternatives

Migration `0016_oracle_read_index` adds a partial `(due_on, id)` index for pending
and postponed occurrences. No financial row is changed, no draft/snapshot table
is created and backup schema 1 remains unchanged. Downgrade removes only the
index. Index construction can briefly block writes and belongs in an ordinary
maintenance upgrade, not an assumed zero-downtime migration.

Rejected alternatives: mutating temporary plans and rolling them back, cloning
financial tables, separately fetching each branch, or allowing a model to
calculate authoritative amounts. A background worker, cache service or model
runtime adds no necessary capability to this slice.

## Consequences and deferred work

The application keeps one deployment and database. Annual source loading and
explanations are synchronous and untruncated; large datasets require measured
performance work. A long read transaction can delay PostgreSQL vacuum cleanup,
though it does not hold financial row locks. Content hashing may conservatively
invalidate a draft after a source change outside its displayed account scope.

Saved scenarios, multiple simultaneous decisions, series edits, fund-funded
purchases, plan-draft transfer, AI input, historical/probabilistic predictions,
budget/debt models and multi-currency remain outside this slice. Existing
Forecast GET endpoints retain their shared-lock snapshot policy and are not
silently converted to a new transaction model.
