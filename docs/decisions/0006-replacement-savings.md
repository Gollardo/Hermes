# ADR 0006: Month-based replacement savings with managed fund reservations

- Status: implemented under the owner-authorized replacement-savings plan
- Date: 2026-09-17
- Product authority: the owner's purchase, inflation and month-end instructions
- Technical bounds and deferred choices: explicitly recorded in the domain contract

## Context

Ordinary funds already own virtual money and enforce per-account coverage.
Their dynamic distribution is based on relative goal completion, not months to
replacement. Scheduling stores day-specific fixed occurrences, whereas this
scenario has no promised day of payment and redistributes a missed month across
the remaining term.

## Decision

Depreciation owns purchase terms and idempotency receipts. Funds owns its
managed reservations, excluded from ordinary distribution but included in all
coverage checks. Depreciation coordinates public posting contracts in one
transaction as the source-lifecycle owner; it writes no foreign private table.
A separate pure Decimal calculator derives the inflation target and schedule
from month-indexed facts. No worker or automatic ledger posting is introduced.

A compound annual rate is applied once across the original term. Monthly
recommendations use net savings before that month. Current-month partial
contributions affect its remaining amount, not its original recommendation.
Future rows are explicitly provisional. Read reconstruction replaces stored
monthly jobs and immutable monthly-snapshot duplication.

## Alternatives considered

- Ordinary funds with zero percentage: dynamic mode could still refill them and
  change their effective percentage. A protected managed distinction is needed.
- A separate virtual ledger: every spending, coverage and forecast path would
  need a second reservation owner and combined locking protocol.
- Recurring transfers: dates and fixed amounts do not represent month-only intent
  or redistribution after missed contributions.

## Consequences

Coverage, free-money forecasting and backup reuse existing financial facts.
Managed transfer facts are protected from independent journal edits/deletion;
correction uses release and reverse transfer. This retains receipt identity.
The first version locks accounts broadly for coherent reads and writes and
returns complete purchase histories. Batch projections/pagination are future
measured work. No new dependencies or deployment infrastructure are required.

Migration `0017_depreciation` is additive and refuses a destructive downgrade.
Old backups remain readable by new code. New backup fields are intentionally
rejected by older application versions. See the
[domain contract](../domains/depreciation.md) for bounds and deferred features.
