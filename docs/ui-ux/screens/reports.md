# Reports screen

## Refresh and URL-state hardening — 2026-10-21

Report type and useful month or custom-range scope are represented in validated query parameters.
After the first successful result, a refresh retains that result with a non-blocking updating
status; a failed replacement request does not present stale data as newly updated.

## Visual refresh — 2026-09-26

Period controls wrap within the workspace; the scoped total is more prominent
and category bars are thinner. Exact values, category disclosure, source links
and report scope remain unchanged.
See [atlas refresh](../atlas-refresh.md). This records implementation under the
owner-authorized redesign, not separate final visual acceptance.

On a successful pointer-driven result or explicit report-context change, the
already-rendered category bars may fill over the shared 320 ms chart motion.
Exact amounts, shares, category labels, loading, errors and empty states remain
static; keyboard, reduced-motion and history navigation skip the effect. See
[interface motion](../motion.md).

The report developed on the intermediate `0.2.0` line and is recorded under
`0.3.0` in the current changelog. It exposes a top-level Reports destination.
Its first report answers how income or expense is distributed over a selected
month or custom inclusive date range.

The category chart is the visual centre. Exact period total and operation count
stay adjacent to it; below, category groups are collapsed by default and reveal
exact operation amounts, dates and visible links back to the corresponding
journal detail. Income and expense are explicit mutually exclusive choices;
period mode remains secondary. Empty, loading and error states must not present
partial data as a complete report. Money uses the project currency symbol and
text dates use a localized form such as “20 January 2025”. Child categories use the leaf name as the main
label and show the root category as secondary context. Category disclosure uses
the same compact chevron pattern as the operation journal and shows the number
of source operations before expansion.

## Multilingual presentation

The implemented RU/EN presentation follows the shared
[internationalization contract](../internationalization.md). Language changes
update screen copy and accessible labels while preserving financial semantics,
user-entered data, dates, selected context and exact monetary payloads.
