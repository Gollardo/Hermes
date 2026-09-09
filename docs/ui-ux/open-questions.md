# Open UI/UX questions

## Use and authority

The implemented interface was accepted as the public-release baseline on
2026-08-18. These questions concern future changes, not release blockers.
Implementation defaults are not automatically permanent owner decisions.
Current behavior and confirmed rules live in [DESIGN.md](../../DESIGN.md),
[domain documents](../index.md#domains) and the relevant screen directions.

Closed prototype tasks and questions already answered by those contracts are
omitted. The decision log below preserves approval provenance without repeating
all accepted rules as an open checklist.

## Forms and journal

- Should optional operation descriptions ever become mandatory? The current
  implementation accepts empty descriptions; a policy change needs owner review.
- Should drafts survive form close, reload or logout, for how long, and which
  fields may be stored locally?
- What operation volumes and search fields should drive performance targets?
- Which saved filters, bulk actions, tags and account running-balance views are
  worth adding beyond current filtering and pagination?
- Is a side panel preferable to the existing modal for future detail workflows?

## Dashboard and reports

- Do future historical blocks need configurable periods, account breakdowns or
  different chart priorities beyond the current monthly summary?
- Should expected events be confirmable directly from Overview?
- Is a quick privacy mode useful? When would configurable widgets be justified?
- Are previous-period comparisons, balance trends or custom reports needed?
- How should future high-cardinality category aggregation disclose full details?

## Funds

- Does the amount target need an optional target date?
- Is a funds-by-accounts matrix useful, and at what entity count?
- Should a future income workflow offer explicit allocation, or expense entry
  suggest the last fund? Current allocation remains deliberate and explicit.
- Should future row priorities change between fund-first and account-first use?

## Plans, scenarios and analytics

- Should Calendar and Forecast share a permanent Plan workspace?
- Are uncertain amount ranges useful beyond the current editable exact amount?
- Which initial scenario commands, risk explanations and actionable warnings
  belong in the approved detailed `2.0.0` design?
- Are external notifications or intraday projections needed beyond the current
  in-app, end-of-day forecast?
- Multi-currency presentation requires a separately approved conversion model;
  a language change does not change currency.

## Navigation, devices and personalization

- Are mobile workflows equal in priority to desktop? Would bottom navigation
  improve them, and which sections would it contain?
- Which minimum viewports, touch targets and browser/accessibility combinations
  should be officially supported?
- Is global search or a command palette justified?
- Are custom icons/colors, onboarding illustrations, adjustable density or
  dashboard reordering useful? Financial values retain the confirmed two-place
  display contract; hiding cents is not an open default choice.
- Should message tone change from the current neutral presentation?

## Decision log

Add entries after approval without rewriting the history of a question.

| Date | Question | Owner decision | Affected documents |
| --- | --- | --- | --- |
| 2026-08-02 | Product focus | Free money is primary; dashboard is an overview with fast operation creation, forecast, debts, and compact trends and analytics. | `vision.md`, `information-architecture.md`, `screens/dashboard.md` |
| 2026-08-02 | Visual direction | Modern neutral premium minimalism; Quixotic as the primary reference; light base and muted green accent; dark mode deferred. | `visual-direction.md` |
| 2026-08-02 | Operation creation | Income and expense are entered in series; category precedes amount; fact date has no time; modal is preferred; ordinary creation needs no separate confirmation. | `screens/operation-entry.md` |
| 2026-08-18 | Current `0.4.0` interface | Implemented navigation, modal composers, screen compositions, and responsive behavior are the first-public-release baseline; future design system and new screens require separate approval. | `../../DESIGN.md`, `vision.md`, `information-architecture.md`, `visual-direction.md`, `screens/` |
| 2026-08-18 | Audit trail | A separate immutable edit and deletion history is unnecessary for the current single-owner product. | `../domains/operations.md`, `../decisions/0001-financial-posting-model.md` |
| 2026-08-18 | Fund rules | Posting, coverage, rounding, remainder, and archive policy in ADR 0002 are confirmed for the current release. | `../decisions/0002-virtual-fund-ledger.md`, `../domains/funds.md` |
| 2026-08-18 | Recurrence constraints | Frequencies, intervals, valid dates, one-year materialization window, and protection of manually changed occurrences are confirmed. | `../decisions/0003-recurring-rules-and-occurrences.md`, `../domains/scheduling.md` |
| 2026-08-18 | UI amounts and percentages | Canonical display uses space grouping, comma, and exactly two fraction digits; input accepts comma and dot; `ROUND_HALF_UP`; exact 100% breakdowns use display-only largest remainder; server precision is unchanged. | `../../AGENTS.md`, `../../DESIGN.md`, `design-principles.md`, `visual-direction.md` |
| 2026-08-18 | North star and scenarios | Hermes primarily answers “What happens if I make this decision?”; Oracle is the capability name, What if? is the action and parallel-scenario mode. Scenarios are ephemeral by default and saved separately. | `vision.md`, `information-architecture.md`, `screens/forecast.md`, `screens/scenarios.md` |
| 2026-08-18 | AI boundary | Local AI is an optional interface to the deterministic core; the complete workflow works without AI, chat creates only a reviewable draft, and never writes a financial fact or plan directly. Conversations are not stored by default. | `../../DESIGN.md`, `../domains/scenarios.md`, `screens/scenarios.md` |
| 2026-08-18 | Risk boundary | The owner may set a stop-loss; Hermes may separately suggest an explainable boundary without automatically replacing the owner value or blocking an operation. | `../domains/scenarios.md`, `screens/scenarios.md` |
