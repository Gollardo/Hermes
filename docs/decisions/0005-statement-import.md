# ADR 0005: Reviewed statement import

- Status: accepted
- Date: 2026-09-10
- Decision owner: project owner, through the implementation request

## Decision

CSV and XLSX share a bounded configurable reader, saved column profiles, a
write-free review and explicit atomic confirmation. Every data row is shown,
regardless of bank status. Blank or invalid data rows remain visible with a
validation message and cannot be posted until the mapping is corrected.
Bank dates are source text only. The user explicitly selects the fact date,
initially for the file and optionally for each row; no bank date is applied.
Future facts remain forbidden by the Operations domain.

Each row can be skipped, posted as a new operation, linked to an existing fact,
or used to confirm one actionable recurring occurrence or one-off plan. A plan
may also be attached to an existing fact without reposting. Amounts retain the
source's exact value; differing planned amounts are replaced only for the
selected occurrence. Original schedule dates, recurrence identity and siblings
remain unchanged. Similarity is advisory, with amount, description and date
reasons. Equal amounts never prove duplication. A user can select any candidate
in the configured date window, even without a similarity reason.

Imports owns profiles and durable receipts. Application orchestration uses
public Operations, Scheduling, Settings and Funds contracts. It does not bypass
ledger rules. A receipt, financial movements, optional fund allocation and plan
confirmation commit in the same transaction. Up to 200 selected rows commit
all-or-nothing, in reviewed source order. Imports serialize through one advisory
transaction lock; selected occurrences are locked before ledger writes.
A domain failure rolls back the complete selected batch.

## Implementation choices

These bounded engineering choices are not promises of broader financial models:

- CSV supports UTF-8/BOM and Windows-1251, comma/semicolon/tab delimiters and an
  explicit decimal separator. XLSX supports worksheet and header-row selection.
- Signed amounts, direction labels and separate debit/credit columns normalize
  into the same exact representation. RUR maps explicitly to RUB; other
  non-base currencies are rejected. Empty currency uses the instance currency.
- Input limits are 5 MB, 2,000 rows including headers, 100 columns, 4,000
  characters per cell and 20 MB expanded XLSX content. No formula execution,
  macros, external links, DTDs or external entities are supported.
- A receipt key combines file bytes, worksheet and physical row number. A
  canonical decision hash detects changed retries. Overlapping/reordered files
  use advisory ledger matching; the implementation does not claim a universal
  bank transaction identity.
- Source files and preview drafts are not persisted. Profiles and receipts are
  portable optional schema-1 backup fields; old readers cannot accept newly
  extended backups. Receipts intentionally survive deletion of an ordinary
  operation and never recreate it automatically. They are provenance, not
  financial movements or immutable audit history.
- The existing non-negative balance and fund-coverage rules apply after each
  posting inside the batch. Source order can therefore matter; the importer
  does not reorder income or invent an opening-balance adjustment to pass checks.

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
against the Operations numeric envelope. The first source row supplies the
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
