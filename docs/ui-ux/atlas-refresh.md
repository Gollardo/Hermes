# Personal financial atlas — interface refresh

## Authority and scope

On 2026-09-26 the owner authorized redesigning the whole application and updating
UI documentation, while retaining functionality and the existing design language.
The preceding visual audit identified repetitive equal-weight surfaces, oversized
headers, delayed primary content and forecast overflow at an intermediate desktop
width. This is an implementation direction under that authorization; exact CSS
values and final visual acceptance are not independently owner-approved tokens.

The light neutral foundation, muted green, human financial language, labelled
navigation, source drill-down and modal composers remain. The visual concept is
personal financial orientation: money available now, purposes assigned to that
money, and known events over time. No new calculation, route, workflow, API,
financial product, saved preference, illustration service or dependency is added.

## Shared composition

- An integrated pale navigation rail replaces the floating white sidebar card.
  Active navigation has both a surface change and a leading marker. All labels,
  groups and desktop collapse preference remain available. Narrow screens start
  with a compact brand/menu row; opening navigation is temporary and selecting
  a destination closes it and focuses the main content. A skip link precedes
  navigation for keyboard users.
- A compact title, supporting scope and primary action share a header separated
  from content by one fine rule. A title identifies the workspace; the primary
  monetary answer receives greater emphasis where it is the screen's purpose.
- Use warm neutral canvas, white working surfaces and one pale green summary
  surface. Panels have thin borders and restrained corners without elevated
  shadows on every group. Overlays retain their depth cue.
- Use the local system sans-serif stack, supporting Cyrillic and Latin without a
  runtime font request. The old explicit Inter preference is removed. A future
  bundled custom font requires script-coverage and licensing verification.
- Keep tabular figures for comparable amounts. Preserve exact two-place money
  and percentage rendering, signs, currency and full-precision API strings.
- Headings, row labels, supporting copy and metadata use distinct sizes and
  weights. Uppercase is limited to short contextual labels. Long amounts and
  controls must reflow instead of forcing the document wider.
- Existing forms retain field order, defaults, error recovery and commit logic.
  Modals and popovers use symmetric, interruptible motion; hover, focus and
  selection remain distinguishable. Keyboard actions are instantaneous and
  reduced motion retains only gentle fades; see [motion](motion.md).
- Do not add promotional heroes, carousels, parallax, stock photography, rolling
  money counters or scroll-pinned working data. Composition follows the task,
  not a landing-page conversion sequence.

## Screen compositions

### Overview

Short title and existing operation action, followed by one current-money summary
next to the explicitly labelled monthly forecast. Within the summary, free money
is dominant and physical/reserved amounts are supporting context. The forecast
minimum, date and ending amount have separate typographic roles. Both sections
stack in the same DOM order on narrow screens. Attention follows and remains
before secondary analytics. Desktop attention entries use compact columns;
mobile retains a sequential list.

The three existing category/fund breakdowns use aligned horizontal bars instead
of donuts. Each entire breakdown row is a focusable link with a visible arrow and readable
14.4 px labels. An explicit scale caption and an unfilled track distinguish
relative magnitude bars from report shares. Every bar is relative to the largest displayed amount within that
breakdown, not a displayed percentage of total. Decorative bar widths use integer
arithmetic on exact decimal strings. Existing top-five/Other aggregation, amount
labels, periods, source links and partial-error boundaries are unchanged.

### Funds

Summary, fund list, reserve, allocation policy and funding actions, physical
coverage and history remain explicit. The fund list now precedes explanatory
panels. Names, goals, balances and progress can be compared in aligned rows;
row actions remain visible. Reserve remains a separate financial concept even
when zero. Allocation percentages and goal progress are still distinct.

### Forecast

Flexible controls wrap before they overflow. Mobile uses a native period select
and retains the selected scope. Safe spend appears above the chart; the other
three figures follow the plot in both DOM and visual order, before the event
feed. Narrow layouts stack these supporting figures without horizontal scrolling. The chart, known-plans notice,
risk states, exact point details and fund projection remain intact. Intermediate
widths use two control columns, wide layouts three, and mobile one.

### Operations and accounts

Compact headers introduce aligned working lists. Day labels provide a quiet
rhythm in the journal. Amounts and row labels have distinct weights; expanded
effects retain their source meaning. Narrow journal rows put the amount below
its description without truncating its digits. Accounts use aligned names and
balances with visible row actions. Filters, totals and pagination are unchanged.

### Calendar and reports

Calendar keeps actionable occurrences before its internally scrollable month
grid. Date and confirmation controls align compactly, with explicit status and
unchanged confirmation behavior. Reports use thin bars, a dominant scoped total,
and a compact wrapping control area; detail disclosure and source links remain.

### Categories, settings, imports and access

Directories use consistent dividers and readable archived text. Settings group
related preferences, security, fund policy, backup and danger actions using the
same surface hierarchy. Import keeps its setup/review separation, with bordered
field groups and an emphasized review summary. Login, first-run setup, unavailable
and loading states inherit the shared typography, palette, controls and surfaces.
Operation and entity composers inherit shared modal styling without replacing
workflows with side panels.

## Verification and limits

Current execution results and remaining gates belong in
[project status](../project-status.md). Verify populated screens at desktop,
intermediate and 390 px widths; check document overflow independently from the
calendar's deliberate internal scrolling. Review long RU/EN copy, large amounts,
keyboard focus, reduced motion and modal field/footer visibility. Tests continue
to cover source links, formatting, language switching and domain behaviors.
Owner visual acceptance, exhaustive accessibility certification and deployment
are separate from local implementation and browser checks.

## Review corrections (2026-09-26)

The owner requested all eleven findings from the follow-up review be corrected.
The implementation retains the light neutral/green language and domain behavior.
Overview summaries no longer stretch each other's height; repeated forecast copy
is shortened while known-plan/free-money scope remains visible. Account lists
place actions below the amount on desktop, matching funds, and below content on
mobile. The account title includes the count; duplicate descriptions are removed,
with balance-edit guidance retained in the composer. Segmented selectors use one
solid green selected state without a forecast-only shadow. Empty account filters
render an explicit “All accounts” display value, separate from the empty model
value and search query. Placeholder text uses the readable muted color.
