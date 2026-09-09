# Forecast

## Status

The owner approved the implemented `0.4.0` composition on 2026-08-18 as the
first-public-release baseline, and its calculation policy matches the domain
contract. The “Oracle · What if?” product direction is confirmed, but its
screen, domain contract, and implementation remain future release scope.

## Screen goal

Show the probable trajectory of money and explain a potential shortfall early.
The forecast is a verifiable baseline built from the current ledger-derived
balance and known future events, not a prediction of user behavior. It exists as
the foundation for future decision comparison, not as a chart to observe for
its own sake.

## Primary user jobs

- choose one account or a compatible combined scope;
- choose a horizon: two weeks, month, quarter, half-year, or year;
- see starting and ending projected balance;
- find the minimum balance and first possible negative date;
- reveal events influencing a chart point;
- understand contributions from income, expenses, transfers, and obligations;
- open an expected event for confirmation, postponement, or cancellation;
- launch “What if?” and compare a temporary scenario with the baseline without
  changing the actual ledger or confirmed plan.

## Important information

- scope and currency;
- actual starting balance with a time marker;
- safe amount that can be spent without taking the known forecast below zero;
- selected horizon and granularity;
- forecast series;
- minimum balance and date;
- first possible negative date;
- chronological list of influencing events;
- status and source of each future event;
- inclusion and exclusion rules available without searching documentation.

## Secondary information

- total expected inflows and outflows;
- breakdown by event type;
- a calendar view of the same timeline;
- archived and cancelled events in a separate diagnostic mode;
- alternative scenarios, assumptions, and uncertainty after the confirmed
  “Oracle · What if?” direction is implemented;
- the historical actual line as context when it does not overload the chart.

## Implemented composition

1. One row for account scope, horizon, and free/all-money mode.
2. One horizontal row of decision KPIs: safe to spend now, minimum, period end,
   and net flow. Cash gap is not duplicated in another KPI card.
3. The primary chart with an actual starting point, forecast line, and
   risk-aware zero boundary.
4. Synchronized timeline and details for the selected day or interval.
5. A compact column of risks and period totals.
6. Contextual disclosure of the free-money model boundary.

The chart and point list are two views of one calculation model. Buttons below
the chart select an exact date and reveal its events, opening balance, net
change, and closing balance.

## Primary actions

- change scope and horizon;
- select a point or range;
- open an influencing event;
- confirm, postpone, or cancel an expected event in its Scheduling workflow;
- open a specific account;
- reset filters;
- in the future, open “What if?” with the current scope and horizon.

The future scenario flow is documented in [Oracle · What if?](scenarios.md).

## Chart presentation

- The actual starting point labeled “Now” is visually distinct from projected
  closing points and always participates in the Y scale.
- The Y domain follows the actual series range with rounded padding. Zero is not
  automatically included in a safely positive range, but appears for a
  negative or near-zero balance.
- Every available closing point remains keyboard-accessible, while visual
  emphasis is limited to events, selection, minimum, and risk; the chart does
  not become a uniformly weighted strip of points.
- Daily end balance may be the baseline display, but same-day ordering requires
  an approved rule.
- A risk threshold has a label and is not encoded only as a red area.
- Tooltip shows exact date or interval, closing balance, net change in the shared
  two-place UI format, and event count. Opening balance and events appear in the
  synchronized detail panel.
- A transfer between included accounts does not change the combined total. In
  single-account scope it appears as an outgoing or incoming movement.
- A long horizon aggregates visual points while drill-down preserves source
  events. If a daily cash gap recovers before a monthly closing point, a
  separate labeled risk marker preserves it and opens the exact day's details.

## Possible states

### No future events

Show the actual starting point and “No known events in the selected period”. A
horizontal line is not called a stable forecast without this explanation.

### Only expected events

Every future point has a clear planned style. Actual data does not extend
visually into the future.

### Possible shortfall

The summary shows first date, minimum, and affected scope. The chart focuses the
first crossing, with concrete events and possible actions nearby.

### Overdue expected event

It is neither silently moved to today nor included in calculation. The screen
shows how many events were excluded in the current scope and links to Calendar.

### Transfers

A transfer between included accounts is neutral in combined scope but remains
available in the explanation. It affects the selected account line in
single-account scope.

### Incompatible currencies

Accounts are not summed without an approved rate and conversion model. The
owner receives separate forecasts or an explicit scope limitation rather than
an approximate hidden total.

### Many events

The chart aggregates according to scale. The timeline uses virtualization or
pagination and day grouping. A type filter does not silently change the
calculation: “hide from list” and “exclude from scenario” are distinct.

### Partial source failure

An incomplete forecast is not presented as complete. The screen names the
unavailable source and offers retry; actual balance may appear separately.

## UX failures to avoid

- a smooth line implying false precision between events;
- a forecast without starting balance or source list;
- mixing a confirmed actual operation with its linked expected occurrence;
- silently excluding overdue or postponed events;
- one style for fact, plan, and approximate amount;
- treating a combined-scope internal transfer as system expense;
- a filter that silently changes the financial scenario;
- a combined total across incompatible currencies;
- a tooltip with only date and amount but no explanation of change;
- risk represented only by red;
- a complex fan chart or probabilistic model without confirmed probabilities.

## Implemented decisions through 0.4.0

- By default, the chart shows free money: physical balance minus current fund
  reserves. An explicit switch includes all money, including allocated money.
- Below the primary forecast, a fund perspective covers the same horizon: a
  large high-contrast chart of ending-balance shares and exact current-to-end
  values. It includes only future transfers explicitly configured for
  percentage allocation. Manual mode uses stored percentages; dynamic mode
  recalculates them sequentially before each top-up from projected fund
  balances using each goal's relative unfilled share.
- In free mode, future expenses do not choose a reserve automatically. A
  transfer explicitly configured for percentage allocation reduces the free
  forecast by the exact allocated amount. The same internal transfer remains
  neutral in total mode.
- The default selection is all accounts and one calendar month.
- Forecast uses exact daily closing balance with no intraday model.
- Overdue events are explicitly excluded; postponed future events are included.
- Approximate amounts, ranges, and what-if scenarios are not implemented.
- One forecast view model derives current, end, minimum, first-negative, total
  income and expense, net flow, and `safeToSpend`. Safe to spend is
  `max(0, minimumBalance)`, so a projected shortfall never leads the interface
  to recommend spending the current balance.
- Decision KPIs, chart, upcoming-event feed, risks, and period totals use one
  dataset and one set of derived metrics. Separate cards show minimum and date,
  period end, and first cash gap; an empty risk state reserves no space.
- Single-account totals separately show nonzero net transfer effect so income,
  expenses, and overall net flow remain arithmetically explainable. Internal
  transfers are neutral in all-accounts total mode; their allocated portion
  appears as a decrease in free money in free mode.
- The primary desktop layout uses a horizontal row of four KPIs and a full-width
  chart. Risks and totals sit below it in two columns; narrow screens stack them
  vertically, and KPIs become a grid or horizontal strip.
- An event list for the selected point appears beside the chart; event actions
  remain in Calendar. Upcoming events and risk items select the same chart date.
- The chart uses `Number` only for screen coordinates. Every displayed and
  domain amount arrives as an exact decimal string from the backend.
- X coordinates represent calendar distance between dates rather than event
  order. During a scope or period change, the old series disappears until the
  response arrives so new controls never label old amounts.
- Every event links to its exact calendar month with source-occurrence focus.
- The Y scale uses rounded monetary ticks and an adaptive domain with upper and
  lower padding. A safe forecast focuses on its real range; a near-zero or
  negative balance includes zero. The area below zero has a light red tint, and
  the negative segment and points become red, so risk is not color-only.
- The X axis thins labels by horizon without losing source precision. Point
  selection happens directly on the chart and reveals an explanation below.
- Two weeks, month, quarter, and half-year show a point for each day; year groups
  by calendar month. Points and labels thin within a responsive chart viewport;
  the chart has no internal scrolling.
- Mouse hover or keyboard focus shows closing balance calculated from exact data
  in the shared two-place UI format, date, change, and event count. Click keeps
  the point selected and reveals its operations below.
- The chart reserves upper space for tooltips. A point near the top opens its
  tooltip downward so the scroll container does not clip it.
- Significant events use points, while permanent labels for every operation do
  not clutter the line. The trend/recommendation layer was removed because it
  did not explain known planned operations and had no approved model.
- Interactive points, timeline, and risk items have focus states and text
  accessibility labels. The amount sign appears in text rather than only color.
  Forecast points use roving tabindex: `Tab` enters once, while `ArrowLeft`,
  `ArrowRight`, `Home`, and `End` move selection. The exact monthly risk marker
  remains a separate infrequent action.

## Multilingual presentation

The implemented RU/EN presentation follows the shared
[internationalization contract](../internationalization.md). Language changes
update screen copy and accessible labels while preserving financial semantics,
user-entered data, dates, selected context and exact monetary payloads.
