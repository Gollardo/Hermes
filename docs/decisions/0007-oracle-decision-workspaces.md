# ADR 0007: Oracle decision workspaces and everyday spending

- Status: implemented within owner-authorized scope; unreleased
- Date: 2026-09-13
- Owner direction: compose multiple kinds of decisions, compare their joint
  consequences and account for ordinary life absent from explicit payments.
- Supersedes: the single-decision UI and persistence exclusions of ADR 0006;
  its exact arithmetic, read-only calculation and financial ownership remain.

## Context

One temporary purchase largely repeats what the existing forecast already
shows. Useful planning requires interacting decisions, payment-account
constraints, recurring effects, alternatives and honest treatment of incomplete
future spending. The owner accepted the preceding analysis and specifically
prioritized estimating everyday spending.

## Decision

Use structured workspaces with independent alternatives on a common coherent
source snapshot. Forecasting owns a detached chronological cash/fund projection;
Scenarios owns overlays, constraints, bounded search and disclosed category
spending envelopes. Extend public reads from Scheduling, Operations, Categories
and Funds. No external runtime, model or worker is needed.

Expand missing recurring dates purely in memory while respecting every persisted
scheduled identity. A complete future schedule must not depend on opening
Calendar, and a read-only comparison must not materialize rows.

Treat an everyday-spending amount as a category/account monthly total. Actual
current-month and named future expenses consume it, preventing double counting.
Use an explicit manual amount or a transparent three-completed-month mean;
show history, exclusions, rolling backtest and unavailable coverage. This is a
bounded initial estimator, not a statistical model selection result.

Use binary search only for a monotone free-expense target outside these envelopes;
use daily enumeration for a one-off date. Account, fund and scope constraints
are checked for every candidate. The result is a proposal, applied explicitly.

Persist only explicitly saved structured hypotheses in `saved_scenarios` with
version conflicts and shared backup support. Migration `0017_saved_scenarios`
adds this independent table; it creates no ledger or scheduling links. Stale
references are retained as reviewable drafts, not deleted automatically.

## Engineering defaults, not separately owner-approved policies

Limits of 5 alternatives, 50 decisions each, 10 envelopes, 100 saved workspaces,
5,000 source/10,000 expanded events and 20,000 history facts bound synchronous
work. Three training months, six displayed completed months, a `0.0001` equal
remaining-day distribution, exact category matching, 100 explicit exclusions,
0–100% expense stress and 0–90-day income delay are implementation defaults.
The owner approved the capability and direction, not claims that these defaults
are statistically optimal or sufficient for every household.

## Alternatives considered

- Adding only repeatable rows to the old form would still omit ordinary life,
  account feasibility, saved comparisons and actionable amount/date search.
- Adding historical spending on top of named plans would double count purchases.
- Treating missing observations as verified zero would create false confidence.
- Statistical/AI models and probability bands need data-quality evaluation and
  a separate scope. A simple visible estimator is inspectable and works locally.
- Writing scenarios into Calendar would mix hypotheses with commitments and
  contaminate the baseline. Stored inputs remain separate.
- A generic optimizer would require goals, priorities, dependencies and explicit
  tradeoffs. Restricted searches have testable correctness and finite bounds.

## Consequences

The system can evaluate combinations that no single-operation chart exposes.
It also exposes an account shortfall despite a positive combined balance. The
same financial invariants apply to manual input, estimation, stress and search.

Ordinary-spending estimates can be poor when imports are partial, categories
are inconsistent or spending is seasonal. Even observed months do not prove
complete history. Backtesting avoids future leakage but has at most three
eligible evaluation months; it is diagnostic, not calibrated confidence.

Calculation is synchronous and returns explanatory data. Very large accounts,
schedules or saved sets require measured read-model/pagination work. Crossing a
resource cap fails explicitly. No full-scale latency guarantee is established.
Same-day fund ordering is deterministic but does not model execution feasibility
within a day. Four-place solver answers retain their exact value beneath the
canonical two-place display.

Downgrading 0017 discards saved hypotheses only. Take a verified backup; older
binaries may reject exports containing the added schema-1 field. Existing
financial migrations, financial rows and encryption envelope remain unchanged.

## Deferred decisions

Plan-draft conversion, live-data acceptance, model choice beyond the baseline,
coverage confirmation, seasonality, automatic outlier detection, goal/debt/budget
constraints, arbitrary optimization, autosave, stored result snapshots and AI
remain outside this implementation. See [domain rules](../domains/scenarios.md)
and [acceptance](../operations/oracle-workspace-acceptance-2026-09-13.md).
