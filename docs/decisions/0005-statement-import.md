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
automatic reconciliation, partial/many-to-one plan settlements, foreign
exchange, PDF/OCR, bank APIs, autonomous classification, external infrastructure
and background workers are outside this slice. Ordinary Calendar confirmation
keeps its established date policy; the imported-fact pathway is explicit.
