# Financial scenarios

## Direction and implemented boundary

Oracle answers “What changes if I make this financial decision?” The owner
confirmed the read-only deterministic direction on 2026-08-18 and authorized
the first implementation on 2026-09-11. See [ADR 0006](../decisions/0006-deterministic-oracle.md)
for engineering defaults and alternatives, and [project status](../project-status.md)
for verification rather than release assumptions.

Scenarios owns typed temporary decisions, comparisons, risk assessments and
source explanations. Forecasting owns the shared exact projection; financial
owning modules expose reads. The module does not own tables or financial writes.

## Supported decisions

- New expense or income with an explicit active account, positive exact amount
  and calendar date. A hypothetical expense uses free money, never an inferred fund.
- Replacement amount on one pending/postponed expected occurrence.
- New date for one pending/postponed expected occurrence, including movement
  across the selected comparison horizon within the next calendar year.

Dates range from application today through its inclusive calendar-year end.
Past/overdue, confirmed and cancelled events are not editable scenario sources.
A comparison uses all accounts or one account involved in the decision. Archived
accounts remain part of actual history; new hypothetical events require active
references. Existing archived references are retained in projected plans, without
claiming that those plans can currently be posted.

## Invariants

- Running, editing and discarding a scenario never mutate financial state.
  PostgreSQL enforces a read-only source transaction; no materialization occurs.
- Baseline and alternative use one MVCC snapshot, currency, application date,
  scope and horizon. Concurrent confirmation cannot duplicate planned money.
- The caller's source identity and selected occurrence version must match;
  changes return a conflict rather than silently switching the baseline.
- Financial inputs reject floats, non-finite values, nonpositive event amounts,
  more than four fractional digits, out-of-envelope values and unknown fields.
  Money remains Decimal and exact JSON strings. Display rounding is separate.
- The overlay replaces one event or adds one hypothetical event in memory.
  It never edits a recurring rule, sibling occurrence or factual operation.
- Chronological fund allocations are recalculated in both branches from their
  identical starting balances. Dynamic allocations observe earlier projected
  replenishments; no cached final delta substitutes for this calculation.
- Internal transfers remain neutral in all-account physical totals. Fund
  allocations can reduce free money. A selected account's fund effects still
  depend on the global replenishment sequence.
- Initial balance and exact daily closings determine minima and risks; annual
  chart aggregation cannot hide a recovered daily cash gap.
- Actual starting balances, planned events, hypothetical changes and derived
  boundaries have distinct provenance. Source links never treat a synthetic
  event as a stored occurrence.
- A projected deficit is a valid result, not authorization for an overdraft or
  a guarantee of posting feasibility.

## Stop-loss and suggested boundary

Stop-loss is an optional, nonnegative user preference in the current form and
scope. It never changes ledger validation. Strictly-below intervals include
start/end, minimum/date and recovery date, or explicit non-recovery within the
horizon. The starting snapshot is evaluated before today's closing balance.

The separate suggested boundary is the baseline's maximum cumulative free-money
drawdown: `max(0, starting - minimum)`. It names its method, source events and
period and is omitted without nonzero planned effects. It is an initial buffer,
shown as a conservative constant warning boundary, not a statistical estimate
of living expenses. Unknown spending and missing plans remain unknown. The
owner can hide the suggestion; it never replaces their own value.

## Sources, lifetime and errors

`GET /scenarios/context` reads existing materialized plans through one year,
account choices, application date and source identity. `POST /scenarios/compare`
returns both cash perspectives, exact deltas, risks, funds and changed events.
The frontend explicitly offers source refresh and preserves draft fields after
network, validation or source-conflict errors. Failed/partial sources are not
presented as zero or replaced with speculative explanations.

Source freshness is limited to persisted occurrences: the user synchronizes
Calendar separately. Closing, resetting, reloading or leaving Oracle discards
the draft. No scenario or conversation is saved in the database or browser
storage. Existing source-combobox recent-selection preferences are UI metadata,
not saved financial hypotheses.

## Deferred capabilities

Named saved scenarios, multi-decision comparison, persistence/retention and
backup policy, fund-funded purchases, plan-draft transfer and series changes
require a future scope. Local AI may eventually translate intent into a reviewed
draft and explain deterministic results; it may never post facts or plans or
calculate authoritative balances. Historical prediction, model packaging,
resource limits and optional retrieval remain undesigned.
