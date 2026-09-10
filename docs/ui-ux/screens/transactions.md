# Transactions

## Status

In `0.1.0-alpha.4`, the journal gained virtual fund movements, server filters by
period, account, type, and category, pagination, expandable detail, editing, and
deletion. Active filters appear as chips; count and net change apply to the
whole selection. Desktop uses dense cards rather than a table. The owner
approved this composition on 2026-08-18 as the first-public-release baseline.
This document does not approve tags, saved filters, search, or bulk editing
before their respective decisions. A separate immutable change history is
unnecessary for the current single-owner product.

The visual refinement on 2026-08-17 preserves the expandable alpha list while
removing nested cards. Entries group by date, show currency and physical
account, filters live in the journal header, and a compact indicator marks
disclosure. Detail clearly separates type, physical movements, and virtual
movements. A table and separate detail layer remain future alternatives rather
than first-release requirements.

Pending one-off plans due on server-provided application today appear in a
separate, explicit attention section before actual operations. The section
states that the plans have not changed the balance, supports editing, and
requires a concise consequence confirmation before applying one plan. Applying
the plan removes it from that section and refreshes the actual journal. Other
one-off plans remain in a distinct secondary section, so an expected event is
never presented as an actual journal row.

## Screen goal

Serve as a precise, fast working journal of actual financial operations: enter
a series of facts, accept a reviewed import, find an operation, verify its
effect, correct a mistake, and open related context.

## Primary user jobs

- browse operations in stable chronological order;
- find an operation by text, amount, or related entities;
- filter by period, account, type, and category;
- open income, expense, transfer, or adjustment;
- see every physical and virtual effect of one operation;
- edit or delete an operation atomically;
- create a new operation in current context;
- create several operations for one day in sequence;
- after import scope exists, use its separate preview and confirmation flow;
- open the related account, category, or fund.

## Important information

A baseline desktop row contains:

- date;
- understandable meaning: description or another approved primary text field;
- operation type;
- affected account or transfer direction;
- category for income or expense;
- participating fund, if any;
- exact amount and currency;
- explicit archived-reference marker where it matters to history.

An account-scoped register may benefit from running balance after each operation
when ordering semantics make it unambiguous. That column may mislead in the
combined journal and must not appear automatically.

## Secondary information

- exact time and timezone after the date model is approved;
- adjustment reason;
- expected-event link;
- created/updated metadata and version history after an audit-model decision;
- technical movements and identifiers in expanded detail;
- notes if description remains optional, and tags only after approval;
- additional selection totals and bulk actions as a proven workflow develops;
  net change across the full filtered selection already exists.

## Managing large data volumes

### Filters

- Baseline filters: period, account, type, and category.
- The filter panel is collapsed by default and opens with an explicit button;
  active chips and reset remain visible without opening it.
- Participating fund and movements appear in expandable details.
- Active conditions appear as chips and in the result heading.
- Reset returns to the screen's explicit default—the entire unfiltered journal,
  not an unknown state.
- Result count and net change apply to the whole selection rather than one
  page. Without an account filter, this is the sum of all physical movements
  and a transfer nets to zero; with a filter, it is the movement sum for that
  account.
- Saved filters remain backlog after `0.4.0` until repeated queries are
  observed.

### Search

Search covers approved text fields and never hides active filters. A result
explains where the match occurred. Exact amount search respects currency and
decimal formats instead of converting through `float`.

### Sorting and pagination

Default ordering follows domain date/time policy and a stable tie-breaker. User
sorting is acceptable for understandable columns. Returning from details
preserves page, scroll position, filters, and selection.

Server-side pagination is the baseline roadmap hypothesis. Infinite scrolling
is unsuitable as the only mode because it obstructs return, totals, and a sense
of selection boundaries.

### Desktop and mobile

The current alpha prototype uses adaptive dense cards on desktop and mobile:
meaning and amount occupy the first row, while date, account, and category sit
beside or below them according to width. A table and separate detail layer
remain directions for future validation rather than descriptions of the
implemented screen.

## Primary actions

- create an operation;
- create a series through “Save and add another”;
- import operations after the separate import pipeline exists;
- open details;
- edit;
- delete with a concrete explanation of consequences;
- apply or remove a filter;
- open a related account, category, or fund;
- duplicate or create from a template after a separate backlog decision;
- select several rows and perform an approved future bulk action.

## Operation details

Detail presents one user operation, not individual ledger rows as independent
facts:

- type, date, amount, and description;
- source and destination accounts;
- category;
- physical movements;
- virtual fund movements;
- expected-event link;
- total effect;
- lifecycle or audit metadata if later approved.

A side panel is preferable on desktop for reading without losing the list.
Complex editing may open a full composer. On mobile, detail may be a separate
route with return context preserved.

## Possible states

### Empty journal

Explain that operations form the balance and offer creation of the first one.
An initial adjustment may appear as a separately named type.

### No filter results

Show active conditions, quick reset, and no matches. Do not suggest a new
operation as though the global journal were empty.

### Many operations on one day

Day grouping is acceptable but does not replace stable ordering. A day total is
distinct from full-selection totals.

### Transfer

Show one row with direction and one user amount. Details expose both movements.
Do not show a transfer as independent expense and income rows in the combined
journal.

### Adjustment

Use a separate type with reason and balance change. Do not disguise it as
ordinary income or expense.

### Archived entities

Historical names remain readable with a quiet “Archived” marker. Selection may
open read-only context or restoration when allowed.

### Deleting or editing with a fund

Detail or confirmation shows physical and virtual effects. After commit, list,
totals, and related dashboard update coherently.

### Loading another page

Current rows remain visible where possible; loading does not alter column
widths. A next-page failure preserves already loaded data and offers retry.

### Concurrent change

The operation is never silently overwritten. The owner sees the current
version, keeps their draft, and reconfirms consequences.

## UX failures to avoid

- separate expense and income rows for one transfer;
- invisible current filters;
- an unlabeled total covering only the visible page;
- mixing expected and actual operations;
- unstable ordering for operations sharing a date;
- hidden fund effect;
- editing account balance directly instead of creating an adjustment;
- endless scrolling without stable return;
- a horizontally clipped desktop table on mobile;
- icon or color replacing textual type;
- deletion from a row action without explaining recalculation;
- resetting filters after returning from details;
- premature payee, tag, and bulk patterns before model approval.

## Questions for prototype validation

- Are description, category, and amount sufficient to find an ordinary
  operation?
- Is a separate account register necessary, or is one journal with scope
  sufficient?
- Which filters are used daily, and which belong under “More”?
- Is running balance needed in account-scoped mode?
- What data volume is normal for desktop and mobile tests?

## Multilingual presentation

The implemented RU/EN presentation follows the shared
[internationalization contract](../internationalization.md). Language changes
update screen copy and accessible labels while preserving financial semantics,
user-entered data, dates, selected context and exact monetary payloads.

## Statement import entry

The journal links to the separate [statement review](imports.md). Imported facts
appear in the same journal and use the same `focus` deep link. Import mapping and
batch decisions do not change the ordinary operation composer.
