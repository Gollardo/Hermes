# UX principles

## Current visual implementation

The owner-authorized [atlas refresh](atlas-refresh.md) applies these principles
through one dominant answer, compact explanatory headers, fewer independent
surfaces and flexible control widths. Domain precision, fact/plan separation,
explicit consequences and recoverable input remain unchanged. The authorization
covers redesign work; it does not certify final visuals or all accessibility
states.

## Status

The current general presentation rules are owner-confirmed. Specific layouts,
the component library, and a future design system are decided separately. When
these principles conflict with confirmed domain invariants, domain
documentation takes precedence.

## Confirmed presentation rules

- Calendar dates outside input fields use localized text, for example `20
  January 2025`. Native date inputs retain the platform format.
- Money uses a familiar currency symbol where possible; the ISO code is the
  fallback for currencies without a mapping.
- Every amount and percentage groups thousands with spaces and shows exactly two
  fraction digits. The canonical rendered form uses a comma: `100 000,00` and
  `12,50%`.
- Amount and percentage fields accept comma and dot as equivalent decimal
  separators: `1000,50` and `1000.50` represent the same exact value.
- Formatting is presentation-only. The API receives a normalized exact decimal
  string without grouping separators; server precision and calculations are not
  reduced to two places.
- Individual values use exact decimal `ROUND_HALF_UP`. When exact server shares
  form a 100% breakdown, displayed hundredths are distributed by a stable
  largest-remainder pass and also total `100,00%`; source percentages do not
  change.

## 1. The decision matters more than the metric

**Why.** A command center should help the owner act rather than display the
largest possible number of metrics. A number without context increases load and
may create false confidence.

**Where it applies.** Dashboard, account and fund summaries, analytics, and
forecasting.

**Good outcome.** The minimum forecast balance includes its date, reason, and a
“View influencing events” action. A card does not appear unless it answers a
distinct user question.

## 2. Facts, plans, and estimates are visibly distinct

**Why.** An expected operation does not change the actual balance, and a
forecast is not a promise. Mixing them is one of the most dangerous financial
UX errors.

**Where it applies.** Dashboard, calendar, forecast, operation details, and
upcoming-event notices.

**Good outcome.** The actual balance is labeled “Now”, expected events have
their own status, and the forecast line has a distinct style and an explanation
of its source data. The distinction survives without color.

## 3. Frequent work is fast; complex work is safe

**Why.** Manual entry may be daily, but income, expense, transfer, and
adjustment have different consequences. Speed must not come from hidden fields
or an ambiguous amount sign.

**Where it applies.** The “New operation” action, journal creation, operation
duplication, and expected-event confirmation.

**Good outcome.** After type selection, the form shows only relevant required
fields, uses safe contextual defaults, and supports keyboard submission. A
transfer always shows source and destination, with a concise preview of both
effects before saving.

## 4. High density is built in layers

**Why.** Financial work requires comparing many rows, but showing every
property at once makes the interface unreadable.

**Where it applies.** Journal, account and fund lists, dashboard, and detail
panels.

**Good outcome.** A journal row shows date, meaning, account, classification,
and amount; technical identifiers and rare fields open in details. The desktop
table remains dense, while a narrow screen turns the row into a semantic
hierarchy instead of clipping a desktop table horizontally.

## 5. Monetary states are exact and unambiguous

**Why.** The owner must distinguish physical balance, reserved money, free
money, and forecast. Formatting must not alter an exact decimal value.

**Where it applies.** Every amount, total, form, chart, tooltip, and export
summary.

**Good outcome.** An account shows “physical balance = in funds + free”.
Currency and sign are visible; all rendered values use the common two-place
format while exact server values continue to drive calculations. A negative
amount has text semantics rather than only a red color.

## 6. Every calculation can be explained

**Why.** Forecasts and aggregates are useful only when the owner can verify them
against source data.

**Where it applies.** Forecasting, expense analytics, account and fund totals,
and dashboard.

**Good outcome.** Selecting a forecast point opens its starting balance and the
events for that date. Selecting an expense category applies a journal filter
instead of creating an unrelated copy of the report.

## 7. Color reinforces meaning but never carries it alone

**Why.** Semantic color supports scanning but depends on theme, color
perception, and cultural context.

**Where it applies.** Risks, statuses, trends, operation amounts, fund progress,
and form validation.

**Good outcome.** A shortfall risk uses color, icon, label, and date. Income and
expense differ by sign, direction, and text; green does not automatically mean
income everywhere.

## 8. The same action behaves the same way

**Why.** Repetition lowers learning time and the number of financial mistakes.

**Where it applies.** Creation, editing, archiving, filters, contextual menus,
detail panels, and confirmations.

**Good outcome.** The primary action has a predictable location, `Esc` closes a
temporary layer, unsaved input is protected, and every archive action explains
its consequences and recovery path.

## 9. Risky changes need a clear consequence, not friction for its own sake

**Why.** Editing or deleting an operation recalculates balances and may affect
funds. Ordinary entry should not suffer from the same heavy confirmations.

**Where it applies.** Operation deletion and editing, archiving entities with
history, backup restore, and fund-allocation changes.

**Good outcome.** Confirmation states which balances and virtual movements will
be recalculated. Ordinary creation completes without another dialog when the
form already shows an unambiguous result.

## 10. An error leaves a path to task completion

**Why.** A message without cause or next action forces repetition and creates
doubt about whether data was saved.

**Where it applies.** Form validation, insufficient balance, edit conflicts,
expired sessions, import, and restore.

**Good outcome.** An edit conflict preserves input, shows the changed version,
and offers “Compare” and “Retry on current data”. A server error never claims
that an operation was saved.

## 11. Progressive disclosure beats premature configuration

**Why.** A beginner needs a clear base model; an experienced owner needs speed
and detail. Making every screen configurable before needs are proven adds
unnecessary complexity.

**Where it applies.** Dashboard, advanced filters, forecast details, fund
properties, and system settings.

**Good outcome.** The primary dashboard has a stable order of key blocks.
Advanced breakdowns and rare fields appear on request. Saved filters emerge
only after a repeated workflow has been demonstrated.

## 12. Privacy and self-hosting are visible where they build trust

**Why.** The owner chose independent data storage, but permanent technical
indicators should not distract from managing money.

**Where it applies.** First run, settings, backup and restore, instance status,
and connection errors.

**Good outcome.** Settings clearly state where data lives, when the last verified
backup was created, and what restore will do. The ordinary dashboard does not
become a server-administration panel.

## 13. A forecast exists to support a decision

**Why.** A chart alone does not answer whether a purchase is safe, a payment
should move, or a plan should change.

**Where it applies.** Forecast, dashboard, funds, future obligations, and the
“What if?” scenario mode.

**Good outcome.** Hermes compares baseline and alternative forecasts, shows the
change in minimum balance and stress window, reveals causes, and allows the
owner to try another date or amount. The answer appears before the chart; the
chart explains the answer.

## 14. Oracle explains; it does not divine

**Why.** A conversational interface is useful only while preserving trust in
the exact financial core. A model can misunderstand text and must not silently
turn an assumption into a financial fact.

**Where it applies.** Natural-language scenario input, conversational analytics,
category suggestions, and forecast explanations.

**Good outcome.** A local model creates a structured draft, the owner verifies
amount, date, and scope, and the ordinary deterministic scenario engine
calculates the result. The same path works without AI. Conversation is not
stored by default, and an operation or plan is created only through a separate,
explicit action.

## Testing the principles in prototypes

Before approving an interaction pattern, test at least these questions:

1. Does the owner understand the difference between physical, free, and
   reserved money?
2. Can they create a typical operation without instructions and then explain
   its effect?
3. Can they drill from an aggregate or forecast to source operations?
4. Are fact, expectation, and estimate distinguishable without color alone?
5. Do precision and meaning survive on desktop and narrow screens?
