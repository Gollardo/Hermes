# ADR 0003: recurring rules and expected occurrences

## Status

Accepted for the current release; recurrence and materialization limits
confirmed by the project owner on 2026-08-18. Richer recurrence remains a
separate future capability rather than an unresolved release policy.

## Context

Hermes needs recurring income, expense and transfer plans without allowing a
plan to affect the physical ledger. Materialization must be bounded and safe to
retry. Editing a rule must not rewrite an occurrence the owner has already
confirmed, postponed or cancelled.

## Decision

Scheduling owns two kinds of records:

- a **recurring rule** is the current template and recurrence definition;
- an **expected occurrence** is a dated snapshot generated from one rule.

Rules support `daily`, `weekly`, `monthly` and `yearly` frequencies. The start
date is the recurrence anchor. An optional end date is inclusive. Weekly rules
select a non-empty unique set of ISO weekdays and repeat every one, two or three
weeks. Monthly rules repeat every one, two or three months on the start day.
Daily and yearly rules use interval one. Monthly rules accept only start days
1–28, and yearly rules reject 29 February, so generation never invents a policy
for a missing calendar day. API validation and database checks enforce the same
frequency/interval/weekday shape.

Materialization covers `[today, today + 1 calendar year]` in the configured
application timezone. Both boundaries are inclusive. A unique
`(rule_id, scheduled_on)` identity and a row lock on the rule make repeated or
concurrent materialization idempotent.
The window is a storage bound, not an implicit rule end: a rule without an end
date produces the next bounded window whenever materialization advances.

An occurrence stores:

- immutable `scheduled_on`, its identity in the source sequence;
- mutable `due_on`, changed by postponing that occurrence or by an explicitly
  enabled future-series shift;
- a complete operation snapshot: type, accounts, category, amount and
  description, plus the transfer-only fund-allocation choice;
- status `pending`, `postponed`, `cancelled` or `confirmed`;
- `manually_modified`, an explicit boundary protecting owner changes;
- a day-offset snapshot that keeps already materialized and newly generated
  dates consistent after a series shift;
- an explicit series-shift preservation marker for automatically cancelled
  dated exceptions; the marker requires `cancelled` status and excludes
  `manually_modified`;
- an optimistic version and, after confirmation, the actual operation link.

Rule edits synchronize only current/future non-confirmed,
non-manually-modified occurrences.
Matching dates receive the new snapshot. Dates removed by the new recurrence or
by disabling the rule are automatically cancelled. Newly matching dates are
materialized. An automatically cancelled occurrence may be restored if a later
rule edit makes its original date valid again. Confirmed, postponed and manually
cancelled occurrences never change implicitly. A series shift marks an
automatically cancelled dated occurrence as explicitly preserved, so later
materialization does not depend on comparing its offset with the rule offset.

Untouched occurrences that become overdue remain actionable. Advancing the
materialization window never cancels or deletes them.

Confirmation locks the occurrence and calls the Operations public posting
contract in the same database transaction. Posting and the `confirmed` link
therefore commit or roll back together. Repeated confirmation returns the same
link and cannot create a second financial operation. Postponing and cancelling
never call Operations and cannot change actual balances.
When the rule's series-shift policy is enabled, postponing also adds the same
calendar-day delta to the rule offset and to later untouched occurrences.
Confirmed, manually cancelled or postponed, already protected automatically
cancelled, and earlier occurrences are preserved. An unprotected automatically
cancelled occurrence keeps its date and receives the explicit preservation
marker.
The request must match both occurrence and rule versions. The rule, selected
occurrence and mutable later occurrences are locked and updated atomically in
deterministic date/id order. Confirmed, manual and already protected exceptions
remain outside the row-lock set because series shifting cannot mutate them. A
single-occurrence postpone does not depend on the rule version when propagation
is disabled.
The owner may review and replace the selected occurrence's operation snapshot
during confirmation, including type, accounts, category, amount, description
and the existing transfer-allocation choice. The reviewed fields are stored as
a manual confirmed snapshot without changing its rule or siblings. Confirming
a future occurrence early posts the actual operation on application today;
today's and overdue recurring occurrences retain their due date as the fact
date. The plan date remains on the occurrence as scheduling history.
When a transfer snapshot requests percentage allocation, application-level
orchestration posts the physical transfer and the Funds-owned allocation before
linking the occurrence. All three effects are atomic; unavailable allocation
configuration fails rather than silently posting only the transfer.

Rule replacement locks the rule and its occurrences before acquiring category
and account reference locks. Confirmation starts with the occurrence and then
uses the same category-before-account order as ordinary posting. If a rule edit
wins, a confirmation carrying the old occurrence version is rejected; if
confirmation wins, the subsequent synchronization preserves that snapshot.

All scheduling values are calendar dates. The application timezone determines
`today`. Creating the first recurring rule locks timezone changes through the
settings API. Migrating an existing schedule to another timezone is outside
this release.

## Consequences

- Expected data is suitable for the calendar and later forecasting but remains
  separate from the financial journal.
- Snapshotting preserves the exact intent shown before confirmation.
- Rule edits require synchronization work but do not surprise owners by
  rewriting manual decisions.
- More expressive recurrences, missing-day policies and timezone migration need
  a future decision rather than hidden defaults.

## Explicit confirmation date extension (2026-09-23)

The owner requested historical confirmation for one-off plans. The public
confirmation command now accepts optional `occurred_on` for both occurrence
sources. An explicit date cannot be later than application today; scheduling
history and sibling occurrences remain unchanged. Calendar and the composer
submit the reviewed date, defaulting to `min(due_on, application_today)`.
Omission preserves the previous source-specific defaults for older clients.
A retry with a different explicit date conflicts with the linked fact; the same
date returns that fact without posting twice. The existing transaction, lock
order, optimistic version and fund-allocation composition are unchanged.
