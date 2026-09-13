# Oracle · What if?

## Implemented workspace

The 2026-09-13 owner-authorized expansion reuses the established light panels,
forms, searchable account/category/plan selectors, details disclosures, inline
confirmation and RU/EN contracts. It does not approve a new design system.
See [domain rules](../../domains/scenarios.md) and
[ADR 0007](../../decisions/0007-oracle-decision-workspaces.md).

“What if?” remains in Plan navigation; Forecast passes its scope and horizon.
The workspace starts without ordinary-spending assumptions and says so explicitly.

## Flow and reading order

1. Inspect source date and the read-only annual schedule expansion policy.
2. Choose name, comparison scope/horizon and minimum free-money buffer. Explicit
   saving is separate from calculating; saved inputs never become plans.
3. Add ordinary-spending categories with exact account/category choices. Select
   a manual monthly total or three-month historical mean. Explain the subtraction
   of actual and planned spending before presenting a prediction. Open history
   to review or exclude exceptional facts, 30 entries per page.
4. Create/copy up to five alternatives. Each contains multiple typed changes,
   explicit funding, recurrence and one/following source edits or exclusions.
   Show the active alternative, change count and enabled state. Disclose manual
   expense/income stress below the decisions.
5. Calculate all alternatives. Summary choices show constraint status, minimum,
   end balance and delta before the comparison chart. Selecting one shows each
   account's free/physical minimum, cash-gap windows and any fund shortfall.
6. Inspect everyday-spending evidence, six historical months, available rolling
   predictions/MAE, monthly amount, planned offset and projected residual.
   Evidence distinguishes manual input, estimate and incomplete history.
7. Inspect the existing exact chart, daily details, sources and downstream funds.
   Stored plans have Calendar links; virtual plans and estimates have labels.
8. Optionally choose an eligible expense for bounded amount/date search. Explain
   eligibility and bounds. Review the proposed result, then explicitly apply and
   recalculate. No solution does not clear inputs.
9. Save, save as new, open or delete a named workspace. Replacing a dirty draft
   requires inline confirmation. Saved-list version conflicts do not overwrite
   another window; reload the list or save a separate copy.

## Shared patterns and states

The repeatable decision/envelope rows and alternative buttons are necessary to
represent jointly evaluated decisions. They reuse existing form controls and
panels; they are a local composition pattern, not a new global component system.
The previous Oracle comparison component renders the selected alternative, so
chart formatting, risk presentation and day exploration remain consistent.

- Source loading and calculations disable dependent controls; duplicate requests
  and late responses cannot relabel stale values.
- Any input edit clears previous calculation and solver results.
- Source conflicts preserve the workspace. Refresh displays changed sources;
  explicit adoption updates versions while retaining edited amount/date. Missing
  sources remain visible errors until replaced or removed.
- API/network/resource-limit errors use stable localized messages and preserve
  the draft. Incomplete history offers manual entry, never silent zero.
- Unsaved drafts are browser-memory only; a visible dirty notice says that
  leaving loses them. No autosave or navigation guard is promised.
- Exact comma/dot input, two-place financial formatting and semantic labels apply
  to every amount, percentage, source option and result. No financial calculation
  uses JavaScript floating point.
- Narrow screens retain the reading order and stack controls. Large results use
  existing supplementary charts/details; risk is never encoded by color alone.

## Interpretation and exclusions

Feasible means the stated daily/account/fund constraints pass under the selected
assumptions. It is not a guarantee about unknown spending or intraday execution.
Baseline drawdown includes configured ordinary-spending estimates and remains a
separate warning boundary. Manual stress is not a confidence interval.

Plan creation, AI input, automatic categorization, probability bands, generic
optimization, autosave and stored calculation history remain deferred. This
screen does not contain a financial posting action.
