# Oracle · What if?

## Implemented first slice

The owner authorized the bounded implementation on 2026-09-11. Oracle uses the
existing light surfaces, forms, searchable source selectors and RU/EN contract.
This does not approve a new design system. Its calculation and limits are in
[Scenarios](../../domains/scenarios.md) and [ADR 0006](../../decisions/0006-deterministic-oracle.md).

The Plan navigation contains “What if?”. Forecast also opens Oracle with its
account and horizon. The mode compares free money by default and separately
shows period-end physical totals; entering it never creates a plan.

## Flow

1. Load source choices and show application date and the materialized-plan limit.
2. Select a purchase/expense, income, occurrence amount replacement or date move.
   Choose scope, horizon and all material inputs explicitly. New expenses do not
   offer a fund source in this slice. Optional stop-loss remains visible.
3. Calculate both branches from one coherent source snapshot.
4. Read the consequence sentence, before/after end balance, minimum/date and exact
   deltas before the chart. Risk sections compare zero, user and system boundaries.
5. Inspect a date, the exact daily opening/closing balance and source events.
   Synthetic events are labeled as hypotheses and have no Calendar source link.
6. Change amount/date and explicitly recalculate, reset, or leave. There is no
   save or plan-creation button in this slice.

## Explanation and risk

The system suggestion explains maximum known planned drawdown and its period.
It does not pretend to infer mandatory living expenses or sufficient historical
coverage. Its disclosure can be hidden without changing the user's stop-loss.
Stress intervals include exact minimum/date and recovery or non-recovery; buttons
select the corresponding day in the shared details. Exact annual risks remain
daily even when the chart displays monthly closings.

Baseline is dashed, alternative solid, zero and stop-loss have textual legends.
The chart is supplementary: a keyboard-operable date input exposes exact daily
values and source links. Affected events include changed downstream allocations;
fund before/after values are explicitly global across accounts. The assumptions
section distinguishes starting facts, known plans and unknown future spending.

## States and responsive behavior

- Loading sources disables entry; loading calculation prevents duplicate submit.
- Changes clear the old result, so controls never relabel old amounts.
- Stale sources require refresh and review before another explicit calculation;
  entered amount/date/stop-loss remain intact.
- Validation and network failures preserve recoverable input. Unknown server
  prose is not rendered; stable codes use shared localized errors.
- No plans does not disable a standalone hypothetical expense or income.
- A change beyond the display horizon is explicitly disclosed.
- Closing, resetting and leaving discard the scenario; late responses cannot
  restore a discarded result.
- On narrow screens the same reading order stacks into one column. Amounts keep
  exact shared formatting, risk is not color-only, and input accepts comma/dot.

## Deferred flows

Saved alternatives and reviewed transfer into a plan composer belong to 2.1.0.
AI-assisted input belongs to 2.2.0 and will not be required for structured use.
Ranges, series edits and expense-from-fund scenarios are not implied by this UI.
