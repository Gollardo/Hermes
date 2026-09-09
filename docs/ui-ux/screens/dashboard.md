# Dashboard

## Status

The owner confirmed the primary product focus on 2026-08-02. After owner review
on 2026-08-12, the first factual overview was implemented: free, physical, and
reserved money, a monthly forecast, today's and overdue events, and recent
operations. A fixed dashboard is preferable to a premature widget builder. The
owner approved the current implemented composition on 2026-08-18 as the
first-public-release baseline.

## Screen goal

Answer four owner-confirmed questions at a glance:

1. How much money is free now?
2. How much will be free after the selected number of days?
3. What will happen if I make this financial decision?
4. Where did most of the money go?

Dashboard must not replace the journal, funds, forecast, or analytics. It shows
a concise set of signals, provides a route to each source, and supports fast
operation creation.

## Primary user jobs

- immediately see free money and its trend;
- verify the total actual balance and account breakdown;
- compare physical money with money reserved in funds;
- notice the nearest obligation or projected shortfall;
- assess debts and liabilities and their trend after that domain exists;
- see major expense categories, income, and account-balance trends;
- create income, expense, transfer, or adjustment;
- open recent operations and understand a recent change;
- move from the summary to the relevant section.

## Important information

### Current state

- free money as the primary number;
- total physical balance across compatible active accounts;
- total money in virtual funds;
- debts and liabilities after the relevant roadmap scope exists;
- changes in key values over a comparable period;
- a short account breakdown with detail navigation;
- an explicit “Now” marker independent of historical filters.

If aggregation across currencies is ever introduced, do not show a combined
total until a conversion-aware model is approved.

### Needs attention

- first projected shortfall with date and amount;
- overdue expected events;
- the nearest large obligation that changes availability;
- inability to allocate or another verified financial-state conflict.

Hide this block when no action is needed; do not replace it with a decorative
“Everything is fine” status.

### Near future

- events in the next 7–30 days;
- total expected inflows and outflows;
- a short forecast preview with the current point, minimum, and a route to the
  full forecast.

### Recent changes

- recent actual operations;
- date, meaning, affected account or accounts, amount, and classification;
- a route to the full journal with context preserved.

### Compact analytics

- current-calendar-month expenses and income across the five largest root
  categories; smaller categories combine as “Other”;
- fund shares of total saved money;
- each share's color marker repeats beside its text label and exact amount, so
  color is not the sole carrier of meaning;
- account-balance trends;
- free-money and debt/liability trends when source data exists;
- drill-down from every aggregate to its source section or journal.

Charts are useful but limited: every visual block must answer one of the main
screen questions.

## Secondary information

- fund-allocation progress;
- archived or empty entity states only when a useful action exists;
- backup or instance information only during a real problem, not as a permanent
  card.

## Proposed block order

1. Title, historical-block period, and “New operation”.
2. Free money first; physical total, money in funds, and debts beside it.
3. Free-money trend and short forecast.
4. Signals requiring attention.
5. Compact expense, income, and account-balance analytics.
6. Recent operations.

Blocks may form an asymmetric grid on a wide screen, but reading order and
keyboard navigation remain sequential. A narrow screen preserves priority from
top to bottom.

## Primary actions

- create an operation;
- open a specific account;
- open a fund or allocation;
- confirm, postpone, or cancel an expected event after Scheduling exists;
- open the full forecast in the selected scope;
- in the future, open “What if?” with current financial context;
- apply a category or period to the journal through drill-down;
- hide sensitive amounts if a privacy mode is separately approved.

## Possible states

### First visit without financial data

Provide one sequential path: create the first account, then categories, then the
first operation. Do not show a grid of empty zero cards.

### Accounts exist but no ordinary operations

Show actual balances and explain the next action, “Add income or expense”. Do
not present an initial adjustment as daily-journal activity without a clear
label.

### Funds are not configured

Free money remains understandable. The block explains virtual purpose and leads
to creating the first fund. Do not depict a fund as a new bank account.

### No future events

The forecast preview shows only the current balance and explains that the
forecast becomes more useful after expected operations are added. Do not draw a
“stable” line as a real prediction when no events exist.

### Shortfall risk exists

Place the risk above secondary analytics. Include date, affected account,
minimum, and a route to causes. An internal transfer does not create a false
reduction in combined scope.

### Long values and many accounts

The summary does not truncate significant digits. The account list limits its
height and leads to the full section; the combined total is never calculated
from only visible rows.

### Partial loading or failure

Related blocks use a coherent state. If the forecast is unavailable, current
balance may remain visible with a clear message, but projected zeroes cannot be
shown as data. Retry applies to the failing block or coherent request set,
depending on the request boundary.

A category-analytics error does not hide current balances, forecast, and
operations already received. Charts show a local error instead of replacing
data with zeroes.

### Expired session

Return to login. Preserve unsaved operation input locally where possible without
retaining sensitive data longer than necessary.

## UX failures to avoid

- equal visual weight for every card;
- dozens of KPIs or an artificial finance score without an action;
- independent period controls that silently change different blocks;
- a combined balance without account and currency composition;
- mixing actual and expected operations in one feed;
- pie charts with many categories and no “Other” aggregation;
- invisible card clicks with no affordance;
- red and green as the only source of meaning;
- advertising, social, or bank-card motifs from references;
- a customizable grid before a stable task set is validated.

## Questions for prototype validation

- What is the default horizon for upcoming events?
- Which two or three charts best answer the main questions without overload?
- Should recent activity occupy more space than compact analytics?
- Is a privacy mode needed when showing the screen to other people?

## Multilingual presentation

The implemented RU/EN presentation follows the shared
[internationalization contract](../internationalization.md). Language changes
update screen copy and accessible labels while preserving financial semantics,
user-entered data, dates, selected context and exact monetary payloads.
