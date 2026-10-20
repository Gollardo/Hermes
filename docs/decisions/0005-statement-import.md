# ADR 0005: Reviewed statement import

- Status: accepted
- Date: 2026-09-10; amended 2026-10-20
- Decision owner: project owner, through the implementation request
- Refinement confirmed by the project owner: 2026-10-20

## Decision

CSV and XLSX share a bounded configurable reader, saved column profiles, a
write-free review and explicit atomic confirmation. Every data row is shown,
regardless of bank status. Blank or invalid data rows remain visible with a
validation message and cannot be posted until the mapping is corrected.
A saved profile maps the statement column that supplies each row's fact date.
The mapped source date is the review default and replaces the mandatory shared
file-level fact date. The review derives its import period from the selected
row dates and keeps every row date editable before confirmation. The profile
stores an explicit expected format for textual source dates; native XLSX date
cells retain their date meaning. Hermes does not heuristically guess an
ambiguous textual date format. Future facts remain forbidden by the Operations
domain. A row with a missing, invalid or future source date remains visible but
cannot post until the user enters a valid non-future fact date or skips it. No
file-level, neighboring-row, period-boundary or current-date fallback applies.
When a source value contains time, Hermes uses its written calendar date without
timezone conversion; the original value remains source context.

Review defaults to the complete inclusive period found in the file and may
narrow it with an inclusive start/end filter. The interface reports excluded
rows and reset restores the complete period. This import-period filter uses
source dates. Confirmation separately shows the posting period derived from the
reviewed fact dates.

If a reviewed fact date moves outside the source-date import period, the row
remains selected. Review shows the discrepancy and the changed posting period;
it does not silently remove the row. Changing the import-period filter excludes
rows from the current confirmation without discarding their browser-draft
edits. Resetting the filter restores those edits. Reloading the page still
clears the non-persisted review draft.

The statement source description remains separate source evidence and may drive
matching and suggestions. A new fact starts with an empty optional operation
description and offers an explicit copy-from-source action. Selecting a plan
uses the plan description; linking an existing fact preserves that fact's
description.

Each row can be skipped, posted as a new operation, linked to an existing fact,
or used to confirm one actionable recurring occurrence or one-off plan. A plan
may also be attached to an existing fact without reposting. Amounts retain the
source's exact value; differing planned amounts are replaced only for the
selected occurrence. Original schedule dates, recurrence identity and siblings
remain unchanged. Similarity is advisory, with amount, description and date
reasons. Equal amounts never prove duplication. A user can select any candidate
in the configured date window, even without a similarity reason.

The default window may be widened explicitly for one row without changing that
row's fact date. Review rows continue to default to skip: a suggestion never
selects new-fact or plan confirmation automatically.

Imports owns profiles and durable receipts. Application orchestration uses
public Operations, Scheduling, Settings and Funds contracts. It does not bypass
ledger rules. A receipt, financial movements, optional fund allocation and plan
confirmation commit in the same transaction. Up to 200 selected rows commit
all-or-nothing, ordered by ascending reviewed fact date and then by source-row
order within one date. The confirmation summary exposes this posting order.
More than 200 selected rows are rejected and the user narrows the import period;
Hermes never silently splits one confirmation into several transactions.
Imports serialize through one advisory transaction lock; selected occurrences
are locked before ledger writes.
A domain failure rolls back the complete selected batch.

## Implementation choices

These bounded engineering choices are not promises of broader financial models:

- CSV supports UTF-8/BOM and Windows-1251, comma/semicolon/tab delimiters and an
  explicit decimal separator. XLSX supports worksheet and header-row selection.
- Source-date parsing supports native XLSX dates and a bounded explicit set of
  textual day-month-year, ISO year-month-day and day/month/year formats, with
  corresponding date-time variants. Arbitrary user-defined date patterns are
  outside this refinement.
- Signed amounts, direction labels and separate debit/credit columns normalize
  into the same exact representation. RUR maps explicitly to RUB; other
  non-base currencies are rejected. Empty currency uses the instance currency.
- Input limits are 5 MB, 2,000 rows including headers, 100 columns, 4,000
  characters per cell and 20 MB expanded XLSX content. No formula execution,
  macros, external links, DTDs or external entities are supported.
- A receipt key combines file bytes, worksheet and physical row number. The
  receipt also retains the parsed source date and source description so reviewed
  provenance remains visible after the source file is closed. It does not retain
  the complete raw row or file. A
  canonical decision hash detects changed retries. Overlapping/reordered files
  use advisory ledger matching; the implementation does not claim a universal
  bank transaction identity.
- Source files, complete raw rows and preview drafts are not persisted. Profiles
  and receipts, including their source date and description, are
  portable optional schema-1 backup fields; old readers cannot accept newly
  extended backups. Receipts intentionally survive deletion of an ordinary
  operation and never recreate it automatically. They are provenance, not
  financial movements or immutable audit history.
- The existing non-negative balance and fund-coverage rules apply after each
  posting inside the batch. Chronological order can therefore matter; the
  importer does not invent an opening-balance adjustment to pass checks.
- Profiles created before mapped source dates remain readable but cannot start
  a new review until the owner selects the date column and text format and may
  then resave the profile. The old shared-date flow is not a hidden fallback.

## Review controls amended on 2026-10-20

Category selection uses the established searchable financial-directory
combobox, filtered by operation type. Results expose the two-level category
path and search both the parent and child names. Planned-payment selection uses
a searchable combobox: suggested candidates remain first, followed by other
eligible plans in the configured window. Each result exposes its date, exact
amount, category and matching reason; search covers description, category,
amount and date.

Category search matches a normalized substring in either level of the displayed
path rather than only the beginning of the full label.

Category results preserve the two-level domain tree. An active root remains a
selectable row; its active children appear beneath it with indentation and the
full parent-child path as supporting text. Archived categories are unavailable
for new facts but remain readable on existing facts.

The same category-search behavior applies to every category combobox in Hermes;
accounts and unrelated directories retain their existing matching behavior.
The existing-fact selector in import also uses a searchable combobox. Likely
duplicates remain first, while search covers date, operation description,
category and exact amount.

Plan candidates are evaluated in a window around each row's editable fact date,
not one shared file date. The default window remains three days before and after
that row. When several compatible rows explicitly close one plan, the resulting
operation uses the plan description rather than the first source description.

These controls improve review only. They do not make similarity authoritative,
change category or Scheduling ownership, or allow an ineligible plan to be
confirmed.

Bulk action, category and plan assignment remain outside this refinement. Every
row still requires its own reviewed posting decision.

Operation details expose the receipt's source date and source description when
the fact came from statement import. This refinement does not add a separate
import-history screen or journal.

## Consequences and exclusions

The user must reconcile the starting balance before importing old history over
an account already initialized with a current balance. Bank reservations,
automatic reconciliation, partial or multi-date plan settlements, foreign
exchange, PDF/OCR, bank APIs, autonomous classification, external infrastructure
and background workers are outside this slice. Calendar confirmation has its own explicit date contract; imported dates
continue to come from the reviewed row decisions.

## Explicit same-date plan groups (2026-09-23)

The owner requested combining several statement purchases against one plan.
The bounded extension accepts explicit `merge_plan_rows` alongside the existing
per-row decisions. Every member must name the same actionable occurrence and
version, statement account, operation type, fact date, account, category and
fund. Only income/expense groups are supported. Transfers, existing facts,
partial settlements and later additions to a closed plan remain excluded.

Every member is validated against its exact source amount, direction and base
currency. The server sums source amounts with Decimal and revalidates the total
against the Operations numeric envelope. The selected plan supplies the
reviewed description. The group posts once at its first selected member's
position in the reviewed batch; remaining members create no additional
financial effects. The review explicitly shows this aggregation and total.
Other decisions retain their relative order. The whole batch stays atomic.

A canonical hash includes all sorted member decisions; each source row receives
its own receipt with that hash and the same operation id. A full unchanged retry
reuses the operation. Changed membership, singleton/subset retries, changed
fields and partially imported groups conflict. Existing single-row hashes are
unchanged. The existing receipt schema already permits several rows per fact;
no migration or backup schema change is needed. Backup/restore preserves group
receipt identities and hashes. Raw files are still not retained: receipts prove
source-row identity, while viewing original source text requires the file again.
