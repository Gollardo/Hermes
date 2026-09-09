# Preliminary visual direction

## Status

The owner confirmed the overall visual axis on 2026-08-02. This document guides
future moodboards, wireframes, and prototypes, but intentionally does not define
CSS values, specific typefaces, a complete palette, or a component library. A
detailed design system remains future work. The owner approved the implemented
`0.4.0` interface on 2026-08-18 as the first-public-release baseline.

## Implemented shared patterns in the current frontend

The direction first applied in `0.1.0-alpha.2` now covers the current `0.5.0`
interface. Its approved release foundation remains the `0.4.0` owner decision,
not a final design system:

- the desktop shell uses persistent side navigation, a separate workspace, and
  a calm local-instance indicator;
- on a narrow screen, navigation becomes a compact multi-row header: every
  current section remains visible without hidden horizontal scrolling, primary
  and administrative links are visually separated, the hide control sits in
  the block's own top row, and lists and forms become one semantic flow;
- a section starts with a shared page header containing context, one primary
  heading, an explanation, and at most one primary action;
- a panel groups one related task; a soft surface, thin border, and moderate
  radius replace heavy shadows and nested cards;
- creation of a key entity appears beside its list and opens a temporary modal
  layer; on mobile, the form becomes one semantic flow;
- login and first-run setup use one split layout: calm product context on the
  left and a focused form on the right;
- primary, secondary, danger, status, empty, and loading states share one
  hierarchy across implemented sections;
- navigation to a new screen returns it to the top so its title and context are
  not hidden by the previous scroll position.

Preserve these patterns in the current interface. Formalizing them as tokens, a
type scale, and a component library requires separate approval of a future
design system.

## Owner-confirmed direction

- a modern minimalist interface with a premium feel;
- Quixotic as the primary reference among the supplied images;
- a light neutral base with a muted green accent;
- soft surfaces, rounded shapes, whitespace, and restrained gradients are
  acceptable;
- the visual character remains neutral rather than heavily branded;
- dark mode is not a current priority.

## Synthesis of supplied references

The research used `530d6495b0473031495f4aa2f8f786f8.jpg`,
`05527702fe0869dbbd3b6b686b8f55fd.jpg`,
`e9fb4e9cfc1764c144d49ab0687f66d1.jpg`,
`e84f19875e5a26de5a43ab240201a956.jpg`, and
`ef72718ba9d31cfb2a7f462411fc094d.jpg`.

| Reference | Useful qualities | Do not copy literally |
| --- | --- | --- |
| Light Coinest dashboard | Clear side navigation, calm green accent, and a useful combination of summary, chart, and journal. | Too many equally weighted cards, a finance score, bank cards, and an activity feed. |
| Dark Apex dashboard | High density, one row of time filters, compact states, and a table. | Glow, decorative background, business metrics, and a QR block. |
| Dark Helios dashboard | Strong hierarchy, restrained palette, one large primary chart, and compact segments. | Investment/watchlist semantics, AI promotion, and low-contrast secondary text. |
| Light OripioFin dashboard | Good balance hierarchy, understandable period controls, and a useful table under the overview. | Wallet/card imitation and a layout designed around bank products. |
| Light Quixotic dashboard | Airy composition, soft surfaces, one accent, and focus on one large chart. | Excess whitespace for dense-data workflows and unrelated avatars or payment actions. |

The five images repeat several traits:

- a neutral background and clearly separated workspace;
- one dominant accent, usually green or a muted purple in dark variants;
- persistent side or top navigation and a prominent section title;
- a modular grid of differently sized cards;
- large amounts, short labels, and compact comparison indicators;
- charts placed near period controls and hover details;
- overview cards combined with a dense recent-events table;
- soft shapes, thin borders, and low visual noise.

The references also expose a risk: a card grid easily becomes a collection of
equally weighted KPIs, decorative bank cards, and unrelated charts. Hermes
should borrow compositional clarity while prioritizing user decisions.

## Character

The confirmed character is a **modern minimalist tool with premium aesthetics
and human language**.

- **Calm:** no aggressive sales, gamification, or alarming full-red screens.
- **Analytical:** exact numbers, good tables, controlled periods, and disclosed
  calculations.
- **Human:** terminology describes the real task rather than ledger internals.
- **Composed:** few surfaces, clear hierarchy, and predictable action placement.
- **Premium:** quality comes from proportions, typography, resolved states, and
  attention to detail rather than shine or decorative luxury.
- **Personal:** funds and future obligations communicate the purpose of money,
  while personalization does not depend on illustrations or avatars.

## Interface density

The desktop direction is moderately dense with enough whitespace in the spirit
of Quixotic. One screen can compare several related values and 8–15 journal
rows without making the whole product feel like a spreadsheet.

Hierarchy controls density:

- state and exceptions requiring attention come first;
- the short-term future and recent changes follow;
- detailed properties live in a detail panel or separate page;
- rare administrative actions live in contextual menus;
- narrow screens regroup data semantically rather than merely shrinking it.

The first version should not offer a compact/comfortable density preference
without proven need. Choose one high-quality baseline density and test it on
real data.

## Typography

- A neutral sans serif with strong Cyrillic and Latin readability.
- A clear but not excessively contrasted hierarchy of headings, explanations,
  and metadata.
- Amounts receive visual priority only when they are the screen's primary
  answer.
- Tabular figures are mandatory in comparable columns, totals, and time series.
- Sign, currency code or symbol, decimal portion, and negative state must scan
  without ambiguity.
- Every rendered amount and percentage groups thousands with spaces and shows
  exactly two decimal places with a comma (`100 000,00`, `12,50%`). Third- and
  fourth-place precision remains in the domain value and calculations but is
  not rendered.
- Uppercase, overly thin weights, and decorative display typefaces are
  unsuitable for primary financial data.

The specific family and size scale require separate approval.

## Color

The confirmed first-prototype axis is light neutral surfaces with one restrained
green product accent. Exact colors are not yet approved.

Direction rules:

- the product accent represents interaction, selection, and focus rather than
  every positive number;
- semantic colors are reserved for risk, success, warning, and information;
- income and expense are not encoded only as green and red;
- large color fills are rare so they do not compete with numbers;
- muted states remain readable, and archived data does not look disabled when
  it remains interactive;
- validate the palette for contrast and common color-vision differences.

## Surfaces and cards

A card is a semantic group, not a mandatory frame around every number.

- One card answers one question or groups one related set.
- It contains a clear title, primary answer, period context, and expected
  action.
- A thin border or surface change is preferable to a heavy shadow.
- Rounded shapes may support the soft character but remain consistent.
- Differently sized cards are acceptable only with clear hierarchy, not for a
  mosaic effect.
- Avoid nested cards and carousels; they hide comparison and add navigation
  levels.

## Tables and lists

Tables are the primary desktop representation for the journal and detailed
financial data.

- Align numbers for comparison and keep a stable starting point for text.
- Column headers are short and support sorting where meaningful.
- Filters remain visible above the table as current context instead of living
  only in a modal.
- A row has a strong enough primary label and calm metadata.
- Hover and selection differ; keyboard focus remains visible.
- Totals state whether they apply to the whole selection or current page.
- Mobile uses a list with the same semantic order; critical data is not hidden
  in horizontal scrolling by default.

## Charts

Use a chart only for a relationship that is harder to understand through two or
three values.

- A line suits actual or projected change over time.
- Bars suit discrete period or category comparison.
- A stacked view is appropriate only when composition matters more than exact
  segment comparison.
- Donut and radial charts are limited to a small number of major shares; a list
  or bars communicate a detailed expense breakdown better.
- Actual and forecast portions are visually distinct.
- The zero line, time interval, currency, and data scope remain visible.
- A tooltip shows the shared two-place UI format, exact date, influencing
  events, and available drill-down; calculations keep exact server precision.
- Smoothing must not imply nonexistent values between points.
- Series colors retain meaning across dashboard, forecast, and analytics.

## Icons

- Use one simple outline or restrained filled set with consistent weight.
- An icon supplements text but does not replace an unfamiliar financial
  concept.
- An operation type may use icon, sign, and text; one arrow is insufficient.
- Category and fund icons may aid scanning but are not required to create an
  entity and never replace its name.
- Decorative illustrations are acceptable in onboarding and empty states when
  they explain the next action; data takes priority on working screens.

## Motion

Motion confirms cause and effect rather than entertaining.

- Short transitions show a panel appearing, a filter applying, or a result
  updating.
- Saving may briefly highlight a new or changed row.
- An amount must not roll through digits in a way that obstructs verification.
- A chart does not replay a long animation for every filter change.
- Honor reduced-motion preferences; no information depends on motion.

## Light and dark themes

The first prototype and current priority use a light theme. Dark mode is
deferred and outside the required scope of near-term UI design.

If it becomes necessary later, it must preserve the semantics, hierarchy, and
accessibility of the light theme, use neutral surfaces, and avoid copying neon
glow from conceptual references.

## Decisions required before a design system

- acceptable dashboard and table density;
- specific typography and neutral/green palette values;
- the role of illustrations, category/fund icons, and personalization;
- target screen sizes and priority of touch/mobile workflows.

## Multilingual shared pattern

The RU/EN foundation retains existing surfaces, navigation and composers.
A labelled native language select wraps within the available width. Runtime
copy, accessible names, validation and dates follow the
[internationalization contract](internationalization.md); stored names and
canonical financial formatting remain unchanged.
