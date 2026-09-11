# Balance forecasting

## Owner-confirmed behavior

Forecast horizons are two weeks, month, quarter, half-year and year. A forecast
can target one account or all accounts combined. The implemented inputs through
`0.5.0` are:

- current actual balance;
- expected income and expense;
- planned transfers.

Owner-confirmed future inputs, not implemented yet, are:

- credit/installment payments;
- debt repayments.

Oracle implements the owner-confirmed scenario comparison direction: one coherent baseline can be
recalculated with structured hypothetical changes to answer “What if?”. The
hypothesis is read-only and cannot become an actual or expected operation
without a separate explicit command. See [Financial scenarios](scenarios.md).

It reports the future balance series, minimum future balance, a possible first
negative-balance date and its exact balance, and the operations influencing
changes. If the starting snapshot is already negative, that current balance is
the first negative value even when today's planned closing later recovers.

The default series represents free money: current physical balances minus
amounts reserved in virtual funds. The owner can explicitly switch to all money,
including reserved amounts. This view choice does not change allocations.
The reserve snapshot comes from the Funds public batch read after Forecasting
has taken shared account locks, preserving the Accounts → Funds lock order used
by coverage-dependent writes.

Free mode starts from today's free balance and applies planned physical effects
without guessing which future expense may consume a reserve. For a pending or
postponed transfer explicitly marked for percentage allocation, it also
subtracts the exact future allocation from free money: the source loses the
full physical transfer, while the destination receives only its unallocated
part as free money. The same transfer remains neutral across all accounts in
total mode. A separate fund projection applies those allocations using the
configured manual or dynamic mode. In dynamic mode it recalculates percentages
before every planned replenishment from projected balances, in `(due_on,
occurrence_id)` order. Confirmed and cancelled occurrences are excluded;
current fund balances remain the starting point and every amount stays an exact
decimal string. The shared Funds calculator weights each incomplete fund by its
relative unfilled target share, so target size alone does not become a hidden
forecast priority while a non-base dynamic pool exists. With 20 or more active
funds, the guaranteed equal base consumes 100% and the projected shares are
equal apart from deterministic closure units.

## Boundary and flow

Forecasting is a read-side calculation. It combines ledger-derived current
balances with public planned-occurrence and obligation contracts, orders their
effects on a timeline and applies exact decimal arithmetic. It cannot confirm or
post expected operations. See the [forecast diagram](../architecture/data-flow.md).

The Scenarios boundary reuses a pure projection calculation with extra
structured events, but an AI adapter cannot supply authoritative balances or
bypass Forecasting's exact arithmetic. Baseline and alternative must share the
same snapshot, scope, horizon, currency and ordering rules.

## Implemented policy (beta.2 baseline, extended through 0.5.0)

- The series starts with today's ledger-derived actual balance. It includes
  actionable `pending` and `postponed` occurrences from today through the
  inclusive horizon end; `confirmed` and `cancelled` occurrences are excluded.
- Overdue actionable occurrences are not silently moved to today. Their count is
  reported for the selected scope so the user can resolve them in the calendar.
- Events are ordered by `(due_on, occurrence_id)`, grouped by date, and applied
  as one deterministic daily closing balance. The minimum and first negative
  date use these closing balances, not an invented intraday order.
- Week, month, quarter and half-year responses contain one closing point for
  every calendar date in the inclusive horizon, including dates without
  events. A year response uses monthly intervals: the first and last may be
  partial months, while intermediate points close on calendar month-end.
- Monthly display aggregation does not reduce risk accuracy: minimum balance,
  first negative date and `first_negative_balance` are still calculated from
  ordered daily event closings before the response is grouped into month
  points. Every source event remains attached to its monthly interval for
  explanation. This lets the year view show the exact first cash-gap value even
  when its plotted point closes later in the month.
- A single-account transfer is outgoing on its source and incoming on its
  destination. An internal transfer has zero effect on the all-accounts total
  balance. In free mode, an explicitly distributed transfer subtracts the
  allocated amount from the destination and combined free balance, while the
  source still shows the full physical outflow. The transfer remains in the
  explanation for that date. Dynamic overflow assigned to the reserve also
  reduces free money; the Oracle slice corrects this previously omitted effect.
- Two weeks ends at `today + 14 days`; month, quarter, half-year and year preserve the
  day of month where possible and clamp to the target month's last day.
- All current account identities, including archived accounts, participate in
  the combined balance because their ledger history still contains physical
  money. A selected archived account can still be inspected.
- Money is calculated with `Decimal`; API money fields are exact decimal strings.
- The fund projection exposes the allocation mode, each event's percentages and
  amounts, each fund's starting/ending percentage, and blocked transfers when no
  incomplete active fund exists. Dynamic allocation respects target capacity
  and places overflow in reserve, without leaving that amount free.
- The current account model has one locked base currency and no per-account
  currency, so all-account aggregation is compatible by construction.
- The calculation is read-only and persists no projection or snapshot. Beta.2
  therefore adds no schema migration.
- One request takes one shared-lock schedule snapshot before account identities
  and ledger movements. Total mode may scope that snapshot to the selected
  account; free mode locks the global actionable schedule once because dynamic
  fund percentages depend on every planned replenishment, then derives the
  selected-account view and overdue count in memory. Confirmation and posting
  use the corresponding exclusive locks in the same Scheduling-to-Accounts
  order, so one forecast cannot count an occurrence in both actual and planned
  money during a concurrent confirmation.
- The application screen materializes Scheduling's rolling one-year window
  before reading the forecast. The forecast GET itself remains side-effect free;
  API clients that bypass the screen must synchronize the schedule explicitly.

## Open questions

- Performance and snapshot strategy once data volume is measurable.
- The consistent read currently holds shared locks for the request and returns
  every explaining event plus up to one point per day for a half-year horizon.
  A selected-account free forecast also locks the global actionable schedule to
  preserve one deterministic allocation sequence.
  Large schedules may require a versioned read projection or another snapshot
  strategy that preserves explanations.
- Whether future multi-currency accounts require separate series or explicit FX
  scenarios; implicit conversion remains prohibited.
- Whether liabilities and debts join the projection after those domains exist.
- Performance of the public projection contract on measured large annual schedules.


## Oracle public projection contract (unreleased 2.0.0 slice)

`forecasting.contracts` exposes `ProjectionSnapshot`, `ProjectionResult` and
`project_snapshot`. The pure projection reuses exact cash and fund calculators
and computes both free and total perspectives from detached source data.
Scenarios supplies hypothetical event replacements without importing private
Forecasting services. Its MVCC source policy is documented in
[ADR 0006](../decisions/0006-deterministic-oracle.md); the existing Forecast HTTP
routes and their shared-lock behavior remain compatible.
