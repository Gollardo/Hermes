# DESIGN.md

## Purpose

This is the primary UI/UX contract for coding agents working on Hermes.

Read this file before creating or changing UI. Detailed product reasoning,
screen directions, unresolved questions, and examples remain under
`docs/ui-ux/`.

This contract is not a final design system. It does not define an approved
component library, type scale, spacing scale, breakpoint set, or complete
palette.

The project owner approved the implemented `0.4.0` interface on 2026-08-18 as
the first-public-release baseline. The current `0.4.6` changes extend its
established patterns. Preserve the established
navigation, modal composers, visual hierarchy and responsive behavior unless a
later owner decision changes them. This approval does not promote incidental
CSS values into a permanent design system or approve unimplemented screens.

## Authority and Scope

- MUST preserve confirmed domain invariants. Domain documentation takes
  precedence over UI hypotheses.
- MUST check the status section of the relevant screen document before treating
  a proposed direction as implemented or approved.
- MUST NOT present roadmap functionality as available before its domain is
  implemented.
- SHOULD preserve implemented UI patterns while their replacement remains an
  open product question.

## Core Principles

1. Lead with the decision the user needs to make, not the number of metrics that
   can be displayed.
2. Keep actual facts, expected events, and forecasts visibly distinct without
   relying on color alone.
3. Preserve exact financial meaning and make every aggregate or forecast
   explainable from its source data.
4. Make frequent actions fast, but show the consequences of complex or
   destructive actions before commit.
5. Build information density through hierarchy and progressive disclosure.
6. Keep defaults, active filters, scope, period, and affected entities visible.
7. Use the same interaction pattern for the same action across screens.
8. Preserve user input and provide a concrete recovery path when an action
   fails.
9. Keep self-hosting visible where it builds trust, not as permanent
   administrative noise.
10. Use human financial language; do not expose accounting internals as the
    primary interface vocabulary.
11. Treat a forecast as a tool for comparing decisions, not as a chart to
    observe in isolation.
12. Keep deterministic financial calculation authoritative; AI may translate
    intent and explain results but must never become the source of financial
    truth.

### Decision scenarios and AI

- MUST distinguish actual facts, confirmed plans, hypothetical scenarios and
  model-derived estimates without relying on color alone.
- MUST compare a what-if result with the same-scope baseline and show the
  changed assumptions, horizon, minimum balance, risk windows and material
  effects.
- MUST keep a scenario read-only until the user separately chooses to save it
  or create a plan draft. A chat or natural-language request never posts an
  operation directly.
- MUST show the structured amount, date, account/fund scope and action inferred
  from natural language before calculation or saving. Missing material inputs
  require clarification and must not be silently invented.
- MUST allow the complete scenario workflow without AI through ordinary
  structured controls.
- MUST treat local AI as an optional adapter between user intent and public
  application contracts. Financial arithmetic, invariants and scenario
  comparison remain exact and deterministic.
- MUST NOT describe an AI-generated estimate as a fact or guaranteed future.
- SHOULD show both the user's configured stop-loss and an explainable
  system-suggested risk boundary when they differ.

## Mandatory Rules

### Layout & Spacing

- MUST give each screen a clear reading order and one dominant answer or task.
- MUST place the page title, current scope or period, and at most one primary
  contextual action in the page header.
- SHOULD group content with hierarchy, whitespace, and surface changes before
  introducing another card or container.
- SHOULD keep desktop financial views moderately dense and move secondary
  properties into details or progressive disclosure.
- MUST use a card only for one question or one directly related group.
- AVOID nested cards, carousels, and mosaic layouts without a meaningful
  hierarchy.
- AVOID giving every KPI or card equal visual weight.
- MUST NOT introduce a new numeric spacing scale as though it were approved; no
  canonical spacing tokens are currently documented.

### Typography & Financial Formatting

- MUST use a neutral sans-serif that remains readable in Cyrillic and Latin.
- MUST preserve a clear hierarchy between headings, primary answers,
  explanations, and metadata.
- MUST use tabular figures in comparable columns, totals, and time series.
- MUST display every monetary amount and percentage with spaces between
  thousand groups and exactly two fractional digits. The canonical rendered
  form uses a comma as the decimal separator: `100 000,00` and `12,50%`. This
  applies to forms after formatting, lists, totals, chart axes and tooltips,
  progress labels, previews and confirmation text.
- MUST treat this as presentation only. Stored values, calculations, API
  decimal strings and domain comparisons retain their full exact precision;
  the UI must not feed its two-digit rendered value back as authoritative data.
- MUST round an independently displayed value with exact decimal
  `ROUND_HALF_UP`, including negative values. For a percentage breakdown whose
  exact server values total 100%, MUST assign visible hundredths by a stable
  largest-remainder pass so the displayed parts also total `100,00%`. This
  smoothing changes presentation only.
- MUST use the familiar currency symbol when mapped; use the ISO code as the
  fallback.
- MUST display localized text dates outside inputs, for example `20 January
  2025`; native date inputs
  retain the platform format.
- SHOULD emphasize an amount only when it is the primary answer of the current
  context.
- AVOID decorative display fonts, excessively thin weights, or uppercase for
  primary financial data.
- MUST NOT treat any current font family or size scale as an approved design
  token set.

### Colors

- MUST follow the confirmed light, neutral direction with a restrained green
  product accent.
- MUST use the product accent for interaction, selection, and focus—not for
  every positive number.
- MUST reserve semantic colors for risk, success, warning, and informational
  states.
- MUST pair semantic color with text, sign, shape, icon, boundary, or another
  non-color signal.
- MUST keep muted and archived content readable when it remains interactive.
- SHOULD use large color fills sparingly so they do not compete with financial
  values.
- AVOID red/green as the only distinction between income and expense.
- AVOID neon glow, aggressive red surfaces, or decorative dark-dashboard
  effects.
- MUST NOT invent an approved palette from the preliminary direction; exact
  shades remain unapproved.

### Components & Data Visualization

- MUST give cards a clear title, primary answer, relevant context, and visible
  affordance when they are interactive.
- SHOULD prefer a thin border or surface change over a heavy shadow.
- MUST keep corner treatment consistent between related surfaces.
- MUST keep icon weight and style consistent.
- MUST pair unfamiliar icons with visible text; icons must not replace a
  financial concept or operation type.
- SHOULD use tables for dense desktop comparison only when the relevant screen
  direction supports them.
- MUST convert dense data into a semantic mobile list rather than a clipped
  desktop table.
- MUST keep active filters visible as chips or equivalent persistent context.
- MUST label whether totals apply to the entire filtered result or only the
  visible page.
- MUST use a chart only when it communicates a relationship better than a small
  set of values.
- MUST expose exact values, period, currency, scope, and drill-down from
  meaningful chart points or segments.
- MUST distinguish actual and forecast series without color dependence.
- AVOID smoothing that implies values between real financial events.
- AVOID donut or radial charts for many categories; aggregate minor categories
  and provide a textual breakdown.
- AVOID charts that cannot be traced to the source operations.

### Forms & Actions

- MUST represent money as an exact decimal value; UI formatting must not alter
  the submitted decimal string.
- MUST accept both comma and dot as equivalent decimal separators in amount and
  percentage inputs, then normalize the value to the API's exact decimal-string
  contract without binary floating-point conversion. Formatting spaces between
  thousand groups are not part of the value and must not make a displayed value
  impossible to edit or submit.
- MUST make operation type explicit instead of encoding it only through the sign
  of the amount.
- MUST ask for the required category before the amount for ordinary income and
  expense entry.
- MUST keep currency, date, selected account, category, fund, and other applied
  defaults visible and changeable.
- MUST show only fields relevant to the selected operation type; disclose rare
  fields progressively.
- MUST avoid validation errors before the user has interacted with a field.
- MUST identify the first missing or invalid field after a save attempt.
- MUST show the expected financial effect before saving a complex operation.
- MUST prevent duplicate submission.
- MUST report success only after the server confirms commit.
- MUST preserve entered data when saving fails.
- MUST close ordinary successful entry without an additional confirmation when
  the effect was already clear.
- MUST require an explicit consequence explanation for destructive or
  recalculating actions.
- MUST use the existing modal composer for ordinary operation creation and
  editing. A general modal-versus-side-panel rule for other entities is not yet
  approved.
- SHOULD provide “Save and add another” where it supports documented serial
  entry.
- SHOULD use the documented searchable combobox pattern for accounts and
  categories; use native select controls for short closed sets.
- AVOID hidden defaults, ambiguous signed amounts, and one long form containing
  every possible property.
- AVOID adding payee, tags, templates, bulk actions, or automatic allocation
  before their product models are approved.

### Navigation

- MUST organize navigation around user questions and tasks, not module internals
  or accounting terminology.
- MUST keep navigation labels visible with icons; icon-only navigation is not
  the baseline.
- MUST separate settings, help, and instance state from primary financial
  navigation.
- MUST use breadcrumbs only for real nesting, not to repeat top-level
  navigation.
- MUST keep the global “New operation” action discoverable through visible UI
  even when a keyboard shortcut exists.
- MUST preserve and expose contextual defaults when entry is opened from an
  account, fund, or another scoped screen.
- MUST return a newly opened route to its beginning so its title and context are
  visible.
- SHOULD preserve filters, page, selection, scroll position, and scope when
  returning from transaction details.
- MUST NOT choose a permanent narrow-screen navigation pattern until the
  documented top-block versus bottom-navigation question is resolved.

### Responsive Behavior

- MUST reorganize content by semantic priority rather than only shrinking the
  desktop layout.
- MUST preserve the desktop reading order when blocks stack on a narrow screen.
- MUST keep critical financial values out of hidden horizontal scrolling.
- MUST use the same meaning and field order in desktop tables and mobile lists.
- MUST keep primary mobile actions reachable before secondary dense content.
- MUST allow the calendar grid to use its documented internal horizontal scroll;
  the actionable attention list remains before it on mobile.
- SHOULD move forecast analytics below the graph and convert KPI rows into a
  grid or horizontal strip on narrow screens.
- MUST test long Russian labels and large financial values without truncating
  significant digits.
- MUST NOT invent official breakpoint or touch-target values; they remain open
  design questions.

### States

- MUST provide explicit loading, empty, filtered-empty, partial-error,
  unavailable, saving, success, and conflict behavior where the screen can enter
  those states.
- MUST make an empty state explain the entity and offer one safe next action.
- MUST distinguish a globally empty dataset from an empty filtered result.
- MUST NOT replace unavailable or partial data with zero values.
- MUST NOT present partial report or forecast data as complete.
- MUST keep already loaded rows visible when loading or retrying another page
  where possible.
- MUST preserve user input, preview values, and manual corrections after a
  recoverable error.
- MUST show which source or block failed when other independent data remains
  usable.
- MUST keep stale forecast values hidden when controls already describe a new
  scope or period.
- MUST provide retry at the same request boundary that failed.
- MUST NOT show decorative “everything is excellent” states when no action is
  required.

### Accessibility

- MUST provide baseline contrast, keyboard navigation, visible focus, and
  reduced-motion support.
- MUST ensure no information depends only on color, animation, strike-through,
  or iconography.
- MUST keep keyboard order consistent with the visual and semantic reading
  order.
- MUST provide visible mouse or touch alternatives for keyboard shortcuts.
- MUST keep meaningful controls and chart points keyboard accessible.
- MUST provide textual labels for financial signs, statuses, risks, and chart
  values.
- MUST keep status text visible inside calendar occurrences; color and
  strike-through are supplementary.
- SHOULD use the documented roving-tabindex behavior for dense forecast point
  series.
- AVOID motion that delays reading, animates amounts through intermediate
  values, or replays on every filter change.

## Reuse Before Creating

- MUST inspect the relevant screen document and its status before introducing a
  variant.
- SHOULD reuse the documented page header, panel, action hierarchy, state
  hierarchy, navigation shell, and operation composer patterns.
- MUST make the same action behave consistently across screens.
- SHOULD extend an existing pattern through progressive disclosure before
  creating a parallel workflow.
- MUST NOT introduce a new pattern merely to imitate an external reference.
- MUST NOT treat preliminary CSS values as approved design tokens.
- MUST surface a need for a new shared pattern when no documented pattern
  satisfies the task.

## UI Modification Rules

- MUST preserve visible scope, filters, defaults, and financial semantics unless
  the requested change explicitly changes them.
- MUST preserve recoverable user input and return context.
- MUST keep current implemented behavior when the replacement remains an open
  UI/UX question.
- MUST distinguish implemented functionality from roadmap or hypothetical
  functionality.
- SHOULD keep neighboring screens consistent in action placement, status
  treatment, terminology, and drill-down behavior.
- MUST verify that a visual change does not make actual, expected, reserved,
  free, or forecast money ambiguous.

## Anti-patterns

### Avoid

- KPI-card grids added only to fill the dashboard.
- Finance scores, guilt, gamification, or opaque recommendations.
- Decorative bank cards, payment-product motifs, advertisements, social feeds,
  investment watchlists, or unrelated business metrics.
- AI assistants or cloud-dependent insights without an approved product model.
- Fake dashboards for domains that are not implemented.
- Unexplained multi-currency totals.
- Mixing expected events with posted operations.
- Showing a transfer as unrelated income and expense rows.
- Editing an account balance directly instead of creating an adjustment.
- Hiding the physical or virtual effect of a fund-aware operation.
- Automatic fund allocation without a visible preview and approved rule.
- Automatically normalizing fund percentages above 100%.
- Hiding rounding remainder.
- Infinite scroll as the only way to browse the journal.
- Resetting filters or scroll context after returning from details.
- Horizontal clipping of financial tables on mobile.
- Hidden card click targets without visible affordance.
- Color-only income, expense, risk, status, or fund identity.
- A stable forecast line presented as a prediction when no future events exist.
- Smooth forecast curves or probability models without supporting data.
- Independent period controls that silently place dashboard blocks in different
  contexts.
- Nested cards, carousels, decorative illustrations in working data screens, or
  excessive equal-weight surfaces.
- Premature dashboard customization, saved views, compact/comfortable controls,
  tags, payees, bulk editing, or custom reports.

## Visual Quality Checklist

After changing UI, verify:

- [ ] The screen has one clear primary question or task.
- [ ] Reading order, alignment, spacing, and surface hierarchy remain coherent.
- [ ] Financial values retain exact digits, currency, sign, and scope.
- [ ] Actual, expected, reserved, free, and forecast values remain unambiguous.
- [ ] Primary and destructive actions show the correct hierarchy and
      consequences.
- [ ] Defaults and active filters remain visible.
- [ ] Loading, empty, filtered-empty, partial-error, saving, success, and
      conflict states are truthful where applicable.
- [ ] Failed actions preserve recoverable input.
- [ ] Desktop and narrow layouts preserve semantic order and significant values.
- [ ] Keyboard navigation, visible focus, contrast, reduced motion, and
      non-color semantics are preserved.
- [ ] Charts expose exact values and drill-down to their source data.
- [ ] No unimplemented domain appears as working UI.
- [ ] The result remains consistent with the relevant screen document.

## Reference Implementations

No canonical reference implementations are currently documented.

`docs/ui-ux/visual-direction.md` records reusable pattern names and current
frontend behavior, but it does not identify source files as approved canonical
implementations.

## Detailed Documentation

- Product vision and boundaries → `docs/ui-ux/vision.md`
- Cross-screen UX principles and confirmed formatting →
  `docs/ui-ux/design-principles.md`
- Visual direction, typography, colors, surfaces, tables, charts, icons, and
  motion → `docs/ui-ux/visual-direction.md`
- Navigation, page structure, controls, entity relationships, and drill-down →
  `docs/ui-ux/information-architecture.md`
- Confirmed decisions and unresolved questions →
  `docs/ui-ux/open-questions.md`
- Dashboard → `docs/ui-ux/screens/dashboard.md`
- Operation composer → `docs/ui-ux/screens/operation-entry.md`
- Transaction journal → `docs/ui-ux/screens/transactions.md`
- Funds → `docs/ui-ux/screens/funds.md`
- Forecast → `docs/ui-ux/screens/forecast.md`
- Calendar and recurring operations → `docs/ui-ux/screens/calendar.md`
- Reports → `docs/ui-ux/screens/reports.md`

## Conflict Resolution

Confirmed domain invariants override UI/UX hypotheses.

If documents under `docs/ui-ux/` appear to conflict, do not guess. Surface the
conflict before implementing the UI change. Open questions and preliminary
directions must not be silently promoted to approved design decisions.

## Runtime language contract

The owner-approved RU/EN foundation uses immediate browser-local selection and
shared catalogs. Follow [internationalization](docs/ui-ux/internationalization.md)
for reactive copy, errors, accessibility labels, dates and contributor checks.
Language selection never changes financial payloads, the mandatory comma-based
money/percentage format, existing names or unsaved form values. Track repeated
controls by stable identity, not translated text.
