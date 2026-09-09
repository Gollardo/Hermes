# 1.1.0 multilingual foundation: plan and implementation record

## Status and scope

Source and documentation audit: 2026-09-09. The owner subsequently approved the
RU/EN proposal and requested its implementation. The runtime slice is implemented;
publication remains a separate action. The [internationalization contract](ui-ux/internationalization.md)
records the resolved decisions and contributor workflow. This plan retains its
initial audit as a before-state, not a claim that the gaps still exist.

Accepted choices: runtime catalogs with Angular Signals and native Intl plural
rules; browser-local language; Russian default/fallback; immediate selection on
setup/login/Settings; unchanged financial formatting; Monday-first calendar and
24-hour timestamps; independently selected RU/EN fresh category templates; and
frontend translation of stable errors with safe HTTP validation metadata.
No schema migration is required or added. Operational hardening remains deferred.

Authority: [repository guidance](../AGENTS.md), [UI contract](../DESIGN.md),
[module boundaries](architecture/module-boundaries.md), [settings](domains/settings.md),
[scheduling](domains/scheduling.md), [backup](domains/import-export.md), and the
[roadmap](roadmap.md). Current implementation checks and historical verification snapshots are recorded
in [project status](project-status.md).

## Initial audit: existing foundation and gaps

- Angular 22 standalone pages have no shared language selection or translation
  catalog dependency in `frontend/package.json`. Russian copy lives in HTML,
  TypeScript, navigation, validators, chart labels and shared components.
- `frontend/src/index.html` fixes `lang="ru"` and a Russian document title.
- `shared/money.pipe.ts` already provides exact BigInt-based ROUND_HALF_UP,
  percentage largest-remainder closure, currency-symbol mapping and ISO fallback.
  `shared/decimal-input.ts` handles exact numeric input and money expressions.
  These are reusable financial contracts, not locale-dependent arithmetic.
- `shared/date-text.pipe.ts` centralizes some dates but hardcodes Russian month
  names and timestamp locale. Scheduling and Forecast also format dates directly.
  Some `en-CA` formatting computes date keys in an application timezone; it must
  not be replaced mechanically as though it were visible English copy.
- `core/auth.service.ts:apiErrorMessage` already maps structured API error codes
  to Russian messages and uses a caller fallback. Translation is not entirely
  absent, but is coupled to Auth and has no language-aware catalog.
- API routes expose structured `detail.code`/`message` for many failures; ordinary
  framework validation and other failure shapes require an explicit inventory.
  There is no global validation exception adapter in `backend/app/main.py`.
- Settings persist currency, timezone, default account and allocation mode,
  with no language field. Category templates in
  `backend/app/modules/categories/contracts.py` contain Russian names which
  become stored editable records on setup.
- Existing frontend specs cover money, dates, input, shared controls and financial
  screens. They are a regression base, not evidence of RU/EN coverage.

## Affected owners and boundaries

| Area | Expected change |
| --- | --- |
| Frontend core/shared | Language state, catalogs, translation API, error adapter, dates, document metadata, shared controls and accessible labels |
| Shell and all implemented pages | Setup/login/status, overview, accounts, categories, operations, funds, scheduling, forecast, reports and settings copy |
| Settings | Language control; backend schema/API only if an instance preference is selected |
| Auth/setup | Pre-authentication language selection and localized validation; preserve session and setup behavior |
| API composition | Inventory error codes and 422 validation; add compatible structured metadata only where frontend mapping is insufficient |
| Categories/setup application | Optional localized templates for fresh setup, through public category contracts |
| Backup and settings backup surface | Required only if a persisted locale is added; test old documents and explicit defaults |
| Financial domain modules | No planned calculation, ledger, recurrence or allocation redesign; translate presentation of their existing enums and outcomes |
| Documentation and checks | i18n contract, contributor guide, affected shared UI directions, status and release notes when implemented |

No new backend business module, translation server or external infrastructure is
needed. Planned Oracle, debts, imports and multi-currency modules remain outside
1.1.0.

## Invariants to preserve

1. Decimal strings/Decimal/NUMERIC remain authoritative. Both languages retain
   `100 000,00` and `12,50%`, exact HALF_UP and deterministic display closure to
   `100,00%`. Accept comma and dot without float conversion. Do not round a
   submitted value merely because the display has two decimals.
2. Locale does not change base currency, exchange rates, application timezone,
   ISO date keys, enum values, identifiers, weekday identity or API payloads.
   Date-only values must not shift through timestamp conversion. Native date
   inputs retain the platform format. Changing timestamp timezone is a separate
   decision: current timestamp formatting uses the browser zone.
3. Preserve non-negative posting constraints, transfer physical neutrality,
   fund/free/reserve distinctions, atomic edits and optimistic conflicts.
   Plans stay balance-neutral until atomic confirmation; forecasts remain
   read-only. Language switching must never submit financial commands.
4. Preserve the settings singleton, currency lock and schedule timezone lock,
   public module boundaries and transaction lock order.
5. Names/descriptions entered or already stored by the owner are data, not
   catalog keys. Never rename existing categories when language changes.
6. Preserve setup atomicity, authentication, CSRF and throttling. Protected
   backup password/ciphertext failures retain one non-diagnostic user message.
   Never expose raw server validation input, secrets or traceback as fallback.
7. A minor release preserves APIs and backup compatibility. Any schema change
   needs a new migration; never rewrite a published migration.
8. Keep established navigation/composers, entered values, focus and context.
   Translate loading, empty, error, success, conflict, tooltips and accessible
   labels as well as normal visible text. Documentation stays English.

## Initial alternatives (resolved by the accepted contract)

| Decision | Proposed baseline and consequence |
| --- | --- |
| Translation mechanism | Runtime catalogs and reactive language state in one SPA. Select a small typed local layer versus a maintained library after evaluating pluralization, extraction, Angular compatibility and tests; no package chosen yet. |
| Persistence | Browser-local language for 1.1.0 keeps the database and backups unchanged and works before login. Instance-wide preference is an alternative owned by Settings, requiring migration, pre-auth precedence and backup defaults. |
| Default/fallback | Propose Russian as default and fallback for continuity, with explicit RU/EN selection. Browser detection, if desired, needs a defined priority below a saved choice. Missing keys should fail CI and use a readable production fallback. |
| Switch behavior | Propose immediate switching without reload and without losing unsaved forms; make selection available on setup/login and in Settings. Exact placement still needs a UI decision. |
| Financial formatting | Existing comma-based rule applies in both languages. English financial separators require a separate owner change to AGENTS.md/DESIGN.md; they are not implied by localization. |
| Dates/calendar | Translate month/day names; retain current calendar structure and ISO weekday semantics. Decide explicit language tags and timestamp timezone without implicitly changing scheduling. |
| New category templates | Propose explicit template language, initially matching selected interface language, applied only during fresh setup. Existing/restored names remain unchanged. Decide whether this enters 1.1.0. |
| Error boundary | Propose frontend translation by stable code plus safe field/type mapping for 422, with generic localized fallback for unknown/network failures. Keep existing HTTP statuses and machine codes compatible; backend prose translation is not required by this approach. |
| Translation governance | Define stable semantic keys, parameters/plurals, financial glossary, reviewer and completeness gate. Community additions modify catalogs and locale registration, not financial business code. |

## Implementation sequence and acceptance

1. **Record the contract.** Resolve the decisions above; inventory user-facing
   literals, error shapes, generated descriptions and template data. Define a
   RU/EN financial glossary (actual, expected, free, allocated, reserve), key
   namespaces, parameter/plural rules and a missing-key policy. Record an ADR
   if the selected mechanism changes cross-module/persistence contracts.
2. **Build and prove one vertical slice.** Add catalogs, language state,
   document `lang`/title and translation helpers. Migrate setup/login and common
   errors first. Verify fallback, persistence and switching with a populated
   form before propagating the mechanism to every screen.
3. **Migrate shared presentation.** Navigation, operation menu, combobox,
   validators, confirmation/status messages and date helpers. Preserve exact
   money/input helpers. Audit pure pipes, computed view models and cached
   strings so a language change refreshes them without losing state.
4. **Migrate financial screens.** Overview/accounts/categories/operations, then
   funds, scheduling, forecast and reports. Include calendar headings, chart
   axes/tooltips, screen-reader descriptions, empty states and conflicts.
   Compare request payloads before and after each language switch.
5. **Complete selected backend edges.** Add missing safe error metadata and
   fresh-template localization only within the agreed scope. If persistence
   is instance-wide, include Settings migration and backup compatibility here.
6. **Verify and document.** Complete the matrix below, run release-relevant
   checks, document adding a translation and update shared UI directions/status.
   Keep 1.1.0 incomplete until both language scenarios pass; publication remains
   a separate release action.

## Required verification

- Catalog parity, valid keys, parameter parity, RU/EN plural cases (including
  0/1/2/5/11/21), unknown locale, missing key and storage-unavailable fallback.
  Scan for untranslated runtime literals with an allowlist for user data and
  machine values; searching Cyrillic alone cannot prove completeness.
- Language selection before/after login, reload and logout; reactive dates,
  translated errors already on screen, metadata and unsaved modal form state.
- Exact money regression in both languages: large and negative values, halfway
  rounding, more than two stored decimals, percentage closure, unknown currency,
  comma/dot input, grouping and expressions. Assert identical API decimal strings.
- Dates across month/year boundaries, leap day and browser/application timezone
  differences; ISO weekdays, calendar ordering and date-only values unchanged.
- Error mapping: known/unknown codes, malformed responses, network errors,
  401/403/409/422/429/5xx, safe field messages, backup authentication failures.
- RU/EN component scenarios for every implemented page and critical flows:
  setup, restore/login, financial entry/edit, fund allocation, plan confirmation,
  forecast/report filters and export. Assert domain effects remain identical.
- Browser acceptance at desktop and narrow widths: long labels, large amounts,
  modal overflow, keyboard order/focus, screen-reader names, charts and calendars.
  DOM unit tests alone do not prove layout or screen-reader behavior.
- If server contracts/templates change: focused API and PostgreSQL integration
  tests for setup atomicity and validation. If settings schema changes: upgrade
  from public 1.0.0, old backup defaults and JSON/protected-backup round trips.
- Before delivery: `make test` (including isolated PostgreSQL integration),
  `make lint`, `make typecheck`, frontend production build and release image
  build as appropriate, plus `make docs-check` and `git diff --check`.
  Record any unavailable environment gate honestly; deferred operational
  hardening does not waive compatibility checks for the changes being shipped.
