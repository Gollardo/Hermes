# Statement import acceptance, 2026-09-10

## User-visible outcome

The journal opens a separate CSV/XLSX import flow with editable format profiles,
all-status row review, explicit file/per-row fact dates, category suggestions,
explainable fact/plan candidates and manual selection. Confirmation posts new
facts, links existing facts or closes individual recurring/one-off occurrences.
Source amounts stay exact. Optional fund expense/transfer effects reuse current
commands. Selected account effects are shown before atomic batch confirmation.
Failures identify the source row and preserve the draft. Successful rows link
to the journal and cannot be submitted again. Deleted originals are identified
on reimport rather than silently recreated.

## Persistence and contracts

Migration `0015_statement_imports` follows `0014_one_off_plans` and adds
`import_profiles` and `import_receipts`. No shipped migration changed. Downgrade
is refused while receipts exist. Backup schema 1 gains optional profiles and
receipts with defaults for older documents; older applications cannot read the
extended payload. No dependency, worker or external infrastructure was added.

## Verification

- Default backend suite: 123 passed, 78 PostgreSQL-gated tests skipped.
- Dedicated PostgreSQL 17 suite: 79 passed, including 9 import integration tests.
- Parser suite: 14 passed, including exact XML numerics, CSV locales, separate
  debit/credit, all statuses, file bounds and unsafe XML rejection.
- Frontend: 176 passed, including 5 new import tests.
- Final focused parser/import reruns passed after authentication and populated
  downgrade assertions were added; no production code changed in that step.
- Ruff lint/format, frontend ESLint/Prettier, translation catalogs, mypy,
  TypeScript and documentation link/fence checks passed.
- Production Docker image built and ran against a temporary PostgreSQL instance.
  Health returned `ok`, `/imports` returned HTTP 200 and `alembic check` reported
  no new upgrade operations. Upgrade, empty downgrade/re-upgrade and receipt
  downgrade refusal were verified.
- Browser acceptance used the owner's supplied XLSX only in the temporary local
  instance: all four operations plus the trailing blank row appeared. The
  pending coffee row matched a synthetic plan by amount; confirmation created
  one expense on the explicitly chosen date and opened the correct journal
  fact. A 390 px viewport had `scrollWidth == innerWidth == 390`. This is not
  exhaustive Safari/VoiceOver or high-volume certification.
- No production database, owner-server deployment, commit or publication occurred.

## Tested invariants

Preview cannot post or materialize. Financial values remain exact. A failed
batch leaves no partial money movements or receipts. Identical/concurrent
retries do not double-post. Changed decisions and stale plans conflict. A linked
existing fact is not posted again. Both sides of a transfer can attach to one
fact without duplicate movements. Recurring rule/sibling snapshots remain
unchanged. Fact dates are user-selected and future facts are rejected. Currency,
account direction, non-negative balances and fund coverage remain enforced.
Backup/restore preserves deduplication and deletion never causes automatic
recreation. Unauthenticated import cannot parse/post through the protected API.

## Boundaries and technical debt

PDF/OCR, OFX/QIF, bank APIs, multi-currency, bank reservations, partial or
many-to-one settlements, automatic matching, immutable audit history, historical
balance repair and background processing remain outside scope. Raw source files
are not persisted and unsaved review state is lost on reload. Exact-file receipts
are durable; changed/overlapping exports rely on reviewable matching and do not
have a guaranteed cross-export bank identity. Source-order posting can encounter
fund/balance constraints even when a reordered batch would succeed; there is no
silent reordering. Profiles currently save by name, without a deletion UI.
Synchronous parsing/matching is bounded and may need a separate scalability
milestone for larger files. Styles inherit the existing account/directory CSS;
style-budget warnings remain. The production initial bundle is 527.64 kB against
a 500 kB warning budget.

## Recommended next action

Review a small real statement against an isolated restored backup, choose the
starting account balance/date explicitly, verify new versus already-recorded
rows and plan links, then separately schedule production migration with a
validated protected backup. The implementation is unreleased.

## Changed files

- [backend/app/api/router.py](../../backend/app/api/router.py)
- [backend/app/application/imports.py](../../backend/app/application/imports.py)
- [backend/app/modules/backup/schemas.py](../../backend/app/modules/backup/schemas.py)
- [backend/app/modules/backup/service.py](../../backend/app/modules/backup/service.py)
- [backend/app/modules/imports/backup.py](../../backend/app/modules/imports/backup.py)
- [backend/app/modules/imports/contracts.py](../../backend/app/modules/imports/contracts.py)
- [backend/app/modules/imports/errors.py](../../backend/app/modules/imports/errors.py)
- [backend/app/modules/imports/models.py](../../backend/app/modules/imports/models.py)
- [backend/app/modules/imports/parser.py](../../backend/app/modules/imports/parser.py)
- [backend/app/modules/imports/router.py](../../backend/app/modules/imports/router.py)
- [backend/app/modules/imports/schemas.py](../../backend/app/modules/imports/schemas.py)
- [backend/app/modules/operations/contracts.py](../../backend/app/modules/operations/contracts.py)
- [backend/app/modules/scheduling/contracts.py](../../backend/app/modules/scheduling/contracts.py)
- [backend/app/modules/settings/contracts.py](../../backend/app/modules/settings/contracts.py)
- [backend/migrations/env.py](../../backend/migrations/env.py)
- [backend/migrations/versions/0015_statement_imports.py](../../backend/migrations/versions/0015_statement_imports.py)
- [backend/tests/integration/test_imports.py](../../backend/tests/integration/test_imports.py)
- [backend/tests/unit/test_import_parser.py](../../backend/tests/unit/test_import_parser.py)
- [docs/architecture/data-flow.md](../../docs/architecture/data-flow.md)
- [docs/architecture/module-boundaries.md](../../docs/architecture/module-boundaries.md)
- [docs/decisions/0005-statement-import.md](../../docs/decisions/0005-statement-import.md)
- [docs/decisions/README.md](../../docs/decisions/README.md)
- [docs/domains/import-export.md](../../docs/domains/import-export.md)
- [docs/domains/operations.md](../../docs/domains/operations.md)
- [docs/domains/scheduling.md](../../docs/domains/scheduling.md)
- [docs/index.md](../../docs/index.md)
- [docs/project-status.md](../../docs/project-status.md)
- [docs/roadmap.md](../../docs/roadmap.md)
- [docs/ui-ux/screens/imports.md](../../docs/ui-ux/screens/imports.md)
- [docs/ui-ux/screens/transactions.md](../../docs/ui-ux/screens/transactions.md)
- [frontend/src/app/app.routes.ts](../../frontend/src/app/app.routes.ts)
- [frontend/src/app/core/api-error.ts](../../frontend/src/app/core/api-error.ts)
- [frontend/src/app/i18n/en.ts](../../frontend/src/app/i18n/en.ts)
- [frontend/src/app/i18n/ru.ts](../../frontend/src/app/i18n/ru.ts)
- [frontend/src/app/pages/imports/imports.css](../../frontend/src/app/pages/imports/imports.css)
- [frontend/src/app/pages/imports/imports.html](../../frontend/src/app/pages/imports/imports.html)
- [frontend/src/app/pages/imports/imports.spec.ts](../../frontend/src/app/pages/imports/imports.spec.ts)
- [frontend/src/app/pages/imports/imports.ts](../../frontend/src/app/pages/imports/imports.ts)
- [frontend/src/app/pages/operations/operations.html](../../frontend/src/app/pages/operations/operations.html)

- [backend/app/modules/imports/README.md](../../backend/app/modules/imports/README.md)
- [Acceptance record](statement-import-acceptance-2026-09-10.md)
