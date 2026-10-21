# Import, export and restore

## Unreleased parser hardening

XLSX row and cell references are length/grammar checked before integer conversion.
Rows must be positive and within 2000; cells must use uppercase supported columns
through `CV` (100), with the row matching their containing row. Long, malformed,
zero or inconsistent references are rejected before financial writes. Sparse
rows, numeric XML as exact decimal text and non-executable formula markers are
preserved. The API admits up to 16 MiB of import JSON before parsing; existing
5 MB decoded-file, 20 MB expanded ZIP and review limits still apply.

## Owner-confirmed import direction

Future import supports CSV and Excel with column mapping, preview, account
selection, likely-duplicate detection and explicit confirmation before writes.
Parsing or previewing cannot mutate domain data. Confirmation delegates writes
to the owning modules and uses appropriate transaction boundaries.

Duplicate detection is advisory: “likely” matches must remain reviewable rather
than being silently discarded.

## Owner-confirmed backup direction

A full portable export contains all financial data and is versioned. Hermes
offers an encrypted `.hermes` file as the recommended option and an explicit
plaintext JSON file for compatibility and inspection. Both export responses use
`Cache-Control: no-store`; this prevents ordinary HTTP caching but does not
protect a plaintext file after the browser saves it.

```text
format
schema_version
app_version
exported_at
```

Restore is transactional: either the complete validated backup becomes the
restored state or no restored changes remain. See the operational
[backup and restore runbook](../operations/backup-and-restore.md).

Money in JSON should use decimal strings when needed to avoid loss of precision.

## Protected Hermes format (version 1)

The `.hermes` file is UTF-8 JSON. Its outer envelope exposes only format,
version, creation time, algorithms, bounded Argon2id parameters, random salt,
independent nonces and Base64 ciphertext. The inner schema-1 payload contains
`app_version`, `exported_at` and the same exact `BackupData` contract as the
legacy export.

Each export generates a random 32-byte DEK. XChaCha20-Poly1305-IETF encrypts
the payload with the DEK. Argon2id derives a separate 32-byte KEK from the
supplied master password and a new random salt; a second XChaCha20-Poly1305
operation encrypts the DEK. The password, KEK and plaintext DEK are never stored
in the file. Key and payload operations use independent 24-byte random nonces.

The reader validates the 72 MiB outer limit, KDF ranges, strict Base64 and all
decoded lengths before Argon2. Unknown versions fail explicitly. Wrong
passwords and authenticated-ciphertext failures share one user-facing error.
Payload AAD is independent of KDF and wrapped-key metadata so a future password
change may rewrap only the DEK; that rewrap operation is not implemented yet.

## Legacy JSON backup format (schema 1)

`0.1.0-rc.1` implements `hermes-json-backup`, schema version `1`. The envelope
contains `format`, `schema_version`, `app_version`, `exported_at`, `data` and an
`integrity` object with a SHA-256 digest of canonical envelope content excluding
the integrity object itself. Money and percentages are JSON strings with no
binary floating-point conversion.

The digest detects accidental corruption; it is not a digital signature and
does not authenticate the file's author. Restore therefore treats every JSON
file as untrusted, applies strict size/schema/domain validation and still
requires destination-owner re-authentication.

The data section contains application settings, accounts, categories, financial
operation headers and physical movements, funds, fund events and virtual
movements, recurring rules and expected occurrences. Stable identifiers,
calendar dates, timestamps, archive state and optimistic versions are retained.
Optional fund targets and recurrence interval/weekday fields are included.
Schema 1 readers supply compatible defaults for backups written before these
fields existed. Fund-event validation preserves the distinct shapes of an
allocation into one account, redistribution of one fund between accounts, and
a transfer between two funds within one account. Restore writes category roots
before children so the serialized UUID order cannot violate the category-tree
foreign key.

Owner credential, password hash, login throttle and sessions are deliberately
excluded: they are security state of the destination instance, not portable
financial data. An initialized target re-authenticates its current owner through
the shared password throttle and ends other active sessions after restore. An
uninitialized target may instead use first-run restore: the destination owner
chooses a new master password, and the new credential/session plus restored
settings and financial data commit atomically. Excluding source authentication
state is the security-first MVP assumption pending owner review; importing it
remains outside scope.

Only payload schema 1 is accepted. Compatibility translation between backup schemas is
not implicit: a future version must add an explicit, tested reader before it
claims support.

## Boundaries

Imports owns staging and mapping, not accounts or ledger tables. Backup owns the
versioned envelope and validator and orchestrates narrow module-owned backup
persistence surfaces. Neither may bypass current domain invariants merely
because data came from a file.

## Open questions

- CSV dialects, date formats and locale-aware decimal parsing.
- Excel formats. Plaintext JSON remains limited to 50 MiB; encrypted envelopes
  are limited to 72 MiB and contain at most a 50 MiB plaintext payload.
- Duplicate fingerprint and conflict-review UX.
- Forward/backward payload compatibility beyond exact schema 1.
- Password-only DEK rewrap, streaming encryption, signatures and automatic
  rotated backups.

## Multilingual compatibility

The RU/EN foundation adds no backup field or schema version. Category names
round-trip verbatim regardless of interface language. Interface language stays
in browser storage. Localized restore confirmation is mapped to the existing
server phrase after exact UI validation; protected-backup authentication errors
retain one non-diagnostic meaning in both languages.

## Statement import implemented on 2026-09-10

[ADR 0005](../decisions/0005-statement-import.md) records the approved mapped
source-date and all-status policy, transaction boundaries, limits and
exclusions. The mapped source date supplies each row's editable fact-date
default; the file no longer requires one shared fact date. Profiles store an
explicit format for textual dates, while native XLSX date cells retain their
date meaning; ambiguous text formats are not guessed. Review may narrow the
complete derived import period with an inclusive start/end filter and reports
how many rows that filter excludes. The filter uses source dates; the review
summary separately derives the posting period from reviewed fact dates.

The profile mapping, bounded date parsing, native XLSX recognition, per-row
preview defaults, explicit legacy-profile upgrade and browser-local period
filter are implemented. Durable receipt provenance and later confirmation
refinements in this section remain in progress; their accepted contract is
recorded here so the slices compose without restoring the removed shared file
date.

A manual fact-date correction outside the source-date filter remains part of
the reviewed selection and expands the displayed posting period with a warning.
Filtering a row out removes it only from the current confirmation; its edits
remain in the browser draft and return when the filter is reset. Reload still
discards the non-persisted draft. Rows without a parsed source date remain
visible for correction or an explicit skip and do not count as period-filtered
rows.

The bounded text formats are day-month-year with dots, ISO year-month-day and
day/month/year, plus their corresponding date-time variants. Arbitrary
user-defined format patterns are not supported in this refinement.

Missing, invalid and future source dates leave their rows visible and blocked
until the user supplies a valid non-future fact date or skips them. No implicit
fallback supplies a date. A source date-time contributes its written calendar
date without timezone conversion; the original cell remains review context.
Legacy profiles remain readable but require an explicit date mapping before a
new review and can then be resaved.
`imports` now owns format profiles and durable per-source-row receipts. CSV and
XLSX normalize exact numeric text without binary floats; preview creates no
financial records, receipts or calendar instances. Profiles are explicitly saved.

Each posted receipt retains only the parsed source date and source description
needed for later provenance and duplicate review; it does not retain the full
raw row or source file. Those fields participate in backup and restore. A
reviewed change to the operation fact date or description does not rewrite its
source values.

Operations may expose those two receipt fields in imported-operation details.
Imports does not add a separate import-history read model or screen.

The statement's source description is evidence, not the user-owned operation
description. It remains available to matching and review. New facts start with
an empty operation description and may copy the source text explicitly; plan
confirmation uses the plan description, while linking an existing fact never
rewrites its description. This source/operation description separation is the
implemented 2026-10-21 refinement slice; durable receipt provenance described
above belongs to a separate slice.

Plan candidates are searched per row around its editable fact date, with the
existing three-day window on either side as the default. An explicitly merged
plan group also uses the plan description instead of the first row's source
description.

The implemented candidate-search endpoint accepts one row's reviewed fact date,
direction, exact amount, source description and window. It returns actionable
plans and existing facts from the owning modules, ranks candidates with advisory
amount, source-description and same-date reasons first, and retains eligible
manual candidates with no reason. The established combobox searches each result
by date, exact formatted or API amount, stored/plan description and category.
Refreshing or widening one row replaces only that row's candidate directory;
it does not change its fact date or another row's draft. A selected candidate
that is no longer returned is cleared for explicit re-review.

Every row defaults to skip even when suggestions are strong. The user may widen
one row's plan window without changing its fact date. Category search matches
within both levels of the displayed category path.

Confirmation creates a fact or links an existing fact and optionally closes one
plan through public module contracts. Explicit same-date groups combine
compatible income/expense rows into one fact and close that plan once; each
source row retains a receipt. Existing-fact links and transfers cannot be grouped.
Group membership and all reviewed decisions participate in retry validation. A
batch of at most 200 selected rows is all-or-nothing and retries are idempotent.
Selected rows post by ascending fact date, preserving source order within one
date; larger selections must be narrowed and are not split automatically.
The server is authoritative for that ordering and the review summary presents
the same effective order before confirmation. A later-row failure rolls back
all earlier financial effects and receipts in the request; completed rows are
excluded from subsequent submissions and keep their journal links.
Probable duplicates remain user decisions; imported rows from the
same exact source cannot be posted twice. A deleted original fact is not
silently recreated by reimport.

Profiles and receipts are optional schema-1 payload fields with empty defaults
for older backups. Restore validates profile mappings and unique receipt keys.
These new backups require a reader that understands the extension; this is not
forward compatibility with older releases. Raw bank files are not backed up.
