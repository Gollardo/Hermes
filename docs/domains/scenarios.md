# Financial scenarios

## Implemented boundary

Oracle answers “Which combination of decisions remains affordable, when and on
which account?” The owner authorized the original deterministic slice on
2026-09-11 and the decision-workspace expansion, especially everyday spending,
on 2026-09-13. Both remain unreleased. [ADR 0007](../decisions/0007-oracle-decision-workspaces.md)
records implementation defaults; [project status](../project-status.md) records
verification. This is deterministic conditional planning, not a probability of
future financial outcomes.

Scenarios owns typed decision sets, saved hypothesis metadata, comparisons,
constraints and spending assumptions. Forecasting owns chronological exact
cash/fund calculations. Financial source modules expose public read contracts.
Only explicit save/delete commands write `saved_scenarios`; calculating never
writes financial state, schedules or saved results.

## Decisions and alternatives

One workspace has a common scope (all accounts or one account), horizon (two
weeks through one calendar year), nonnegative minimum free-money buffer, up to
10 everyday-spending envelopes and 1–5 named alternatives. Each alternative has
up to 50 enabled/disabled decisions and its own manual stress assumptions.

- New expense, income or transfer with explicit accounts, positive exact amount
  and date. Income/expense may have a typed category. An expense can explicitly
  use one active fund on its payment account. Transfers can allocate their
  destination amount through the existing manual/dynamic fund policy.
- New events can repeat daily, weekly, monthly or yearly until an explicit date.
  Existing recurrence constraints apply: monthly start day at most 28; no yearly
  February 29. All dates stay within today's inclusive one-year window.
- Edit an actionable source's amount and/or date, or exclude it. Apply to one
  occurrence or that recurring series from the selected scheduled identity
  onward. A series edit deliberately includes actionable postponed siblings;
  confirmed/cancelled identities remain excluded. No recurrence rule is written.
- Overlapping edits/exclusions of the same source in one alternative are
  rejected. Alternatives are independent; disabling a valid decision removes
  its projection effect. Syntactic validation still applies to disabled drafts.
- Expense stress increases all projected expenses and monthly spending envelopes
  by 0–100%; income stress delays projected income by 0–90 days. Neither changes
  posted history or the common baseline. These are user-selected stress cases,
  not probability bands. Events pushed outside the display horizon are disclosed.

A comparison can inspect any existing account; new events and spending envelopes
require active references. Existing plans retain archived historical references
without promising that they could be posted. Fund purchases require coverage on
the specified account; no implicit fund-to-account or free-money fallback exists.

## Everyday spending

The user opts in by exact expense category and account. Descendants are not
implicitly included, and duplicate category/account envelopes are invalid. An
envelope is the **total monthly ordinary spending**, not an extra amount on top
of every named purchase. The default is no envelope, with a visible warning that
unplanned spending is absent. Two explicit input modes are available:

1. Manual nonnegative monthly amount, including zero.
2. Mean of the previous three completed calendar months, after selected outlier
   exclusions. Each training month must contain an observed matching expense
   before exclusions; otherwise history mode fails and manual input is offered.

History contains posted expenses only, from six completed months through today
inclusive. Transfers, adjustments and fund-backed expenses are excluded. Up to
100 explicitly selected fact IDs per envelope can be omitted as exceptional;
those facts also do not consume the current month's ordinary envelope. Facts
remain in the ledger. The user can inspect dates, descriptions and exact amounts.

For each affected month:

`remaining = max(0, monthly envelope - current-month posted ordinary spending - named future ordinary spending)`

Today's posted expenses are already in the opening balance and consume the
current-month envelope. Future named expenses include the baseline schedule and
that alternative's decisions in the same category/account, excluding fund
purchases. They consume the envelope once. Removing a routine plan can therefore
increase the estimated remainder instead of falsely eliminating ordinary life.
Named spending above the envelope is retained in full; no negative estimate or
refund is invented. Stress uses stressed named amounts and a stressed envelope.

The remainder is spread evenly over the remaining calendar days of that month,
starting today. Exact `0.0001` remainder units go to earlier days deterministically.
Only days inside the display horizon are emitted. A known payment later in the
same month still consumes the monthly envelope even if outside that horizon.
The disclosed offset refers to whole monthly envelopes; projected residual
refers only to emitted days. Day-level timing is an assumption, not learned
weekday behavior. Planned category assignments can themselves be incomplete.

Evidence includes six monthly actual totals, the monthly estimate, source IDs,
planned offset and added residual. History-mode backtesting predicts each
eligible completed month from its three preceding months only. All four months
must have observed facts. Mean absolute error (MAE) uses only those eligible
predictions; otherwise it is absent. Manual inputs have no model MAE. Backtest
values evaluate the unstressed historical method, not a selected future stress.
Missing records never establish full coverage: `coverage_verified` is always
false. Zero after explicit exclusions is valid but is not proof of no expenses.
Seasonality, trends, inflation and automatic outlier classification are absent.

## Snapshot, projection and invariants

- Baseline and all alternatives share one database-enforced read-only,
  repeatable-read snapshot, currency, application date, scope and horizon.
- Scheduling supplies actionable persisted occurrences plus missing recurrence
  dates in memory. All persisted scheduled identities suppress regeneration,
  including confirmed, cancelled and postponed occurrences. Virtual IDs are
  deterministic; no Calendar materialization command is called.
- Source identity includes balances, plans, fund positions/reserves, settings,
  categories and relevant history. A stale identity or occurrence version
  returns a conflict. Explicit refresh/review is required; no silent rebasing.
- Decimal/NUMERIC and exact JSON strings are authoritative. Floats, non-finite
  values, unknown fields, excess scale, invalid references and event shapes fail
  validation. Four-place calculations are not rounded for two-place display.
- Physical transfers are neutral across all accounts. Per-account free and total
  balances remain separate, so money on another account cannot hide a shortfall.
- Fund calculations reuse public exact allocation functions in `(date, event ID)`
  order. An explicit fund expense releases its covered reservation, and dynamic
  reserve can refill incomplete targets on the reserve's original accounts.
  Later allocations see those projected fund balances. No money moves physically
  between accounts during reserve refill.
- Insufficient fund coverage returns a funding issue and an infeasible result.
  The diagnostic projects the full requested physical outflow while releasing
  only covered reservation. This explains the deficit; it is not an authorized
  fallback or a postable financial operation.
- Initial values and every daily closing determine risks, even on annual charts.
  Intra-day cash ordering is not modelled; the deterministic ID order for fund
  allocation is not a promise about real payment execution order.
- Facts, persisted plans, virtual plans, decisions and derived spending have
  distinct provenance. Virtual events never link to nonexistent Calendar rows.
- Calculation is bounded to 5,000 annual source events, 10,000 expanded events
  per alternative and 20,000 expense history facts. Limits fail explicitly,
  never silently truncate. History limit currently also blocks workspace loading.

## Constraints and bounded search

An alternative meets conditions only when the selected scope's minimum free
balance is at least the buffer, every account's free and physical minima are
nonnegative, and all explicitly selected funds cover their expenses. Shortfall
against the scope buffer and account/fund failures are reported separately.
This is conditional daily feasibility, not authorization to post an operation.

Search supports one enabled, new free-money expense outside everyday-spending
category/account envelopes. Other decisions and assumptions are held fixed:

- Maximum amount: binary search at exact `0.0001` resolution up to an explicit
  positive ceiling, including a recurring expense's per-occurrence amount.
- Earliest date: day-by-day search from the expense's entered date through the
  selected horizon; only one-off expenses are eligible.

The target date must be inside the display horizon. Fund-funded expenses,
overlay edits, envelope-consuming expenses and arbitrary optimization are
unsupported targets. The restricted amount target preserves monotonicity.
No solution is explicit. A found result never changes input until the user
applies it, then all alternatives are recalculated. Exact four-place values are
retained when displayed with two fractional digits.

The separate baseline drawdown boundary is `max(0, initial free - minimum free)`.
It includes selected ordinary-spending estimates and is a disclosed constant
warning boundary; it does not replace the user's constraint or represent a
statistical living-cost reserve.

## Saved lifecycle, API and errors

The workspace routes are `GET /scenarios/workspace-context`,
`POST /scenarios/workspaces/compare` and `/solve`, and CRUD `/scenarios/saved`.
The original `/context` and `/compare` retain their single-decision compatibility
contract and materialized-only source policy.

Explicit saving retains name, structured inputs, source identity and optimistic
version; it never saves results, conversations or source copies. Up to 100 saved
workspaces are supported. Update/delete require the current version. Concurrent
conflicts preserve the draft and allow an explicit new copy. Draft references
may become stale or missing; saving is structural validation, calculation is
fresh financial validation. Opening a saved draft does not silently update it.

Saved hypotheses participate in the existing atomic backup/restore, including
protected exports. Schema-1 documents without `saved_scenarios` restore an empty
collection. Older readers are not promised forward compatibility with this new
field. No new encryption envelope or raw history storage is introduced.

Network, validation, resource-limit and stale-source errors retain inputs;
unknown server prose is not displayed. Refresh shows changed source values and
requires explicit adoption, retaining entered amount/date. Missing sources must
be replaced or removed. Editing invalidates old results; late responses cannot
restore a discarded calculation. Unsaved edits remain in browser memory only;
leaving/reloading loses them. Save before navigating away.

## Outside this scope

Plan-draft conversion, posting from Oracle, debt/loan models, budgets, currencies
and exchange rates, AI/chat, Monte Carlo/probability bands, automatic history
classification, trend/seasonal models, generic optimizers, background workers,
autosave and stored calculation archives remain separate work.
