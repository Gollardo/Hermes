# Internationalization contract

## Accepted scope

The owner approved the RU/EN implementation proposal on 2026-09-09. The
implementation is a runtime presentation layer within the existing standalone
Angular application. No translation server, financial-domain dependency or
additional package is introduced. The native `Intl.PluralRules` implementation
owns plural selection; Hermes supports plain named parameters rather than a
custom ICU message language.

The [implementation plan](../multilingual-foundation-plan.md) retains the
source audit and delivery sequence. The current verification evidence is in
[project status](../project-status.md).

## Language selection and state

- Russian is the initial language and explicit fallback. There is no browser
  language detection in this release.
- A selector using the names `Русский` and `English` is available throughout
  setup, on login and in Settings. Language names use their native spelling;
  flags are not used.
- Selection is saved under `hermes-language` in browser local storage. The
  preference is origin-specific and remains after logout. There is no server
  language setting, migration or language field in backups.
- An unknown stored selection falls back to Russian. If browser storage is
  unavailable, selection remains usable for the current application lifetime.
- Switching requires no reload and performs no HTTP request. Templates,
  accessible labels, document title and document `lang` update reactively.
  No account, category, operation, date, currency, timezone or form value is
  changed. Separate already-open tabs do not automatically synchronize.
- Existing error and success state stores a deferred message recipe rather
  than rendered prose. Translation and formatted date parameters are evaluated
  when displayed. User-entered names/descriptions are plain data and never
  interpreted as translation keys or HTML.

## Formats and terminology

| Concept | English interface term |
| --- | --- |
| Physical money location | Account |
| Virtual money purpose | Fund |
| Unallocated available money | Free balance |
| Excess set aside in dynamic mode | Reserve |
| Expected, unposted event | Planned operation / occurrence |
| Posted financial record | Posted operation / actual |
| Read-only future calculation | Forecast |

Money and percentages in both languages retain the exact presentation contract:
`100 000,00`, `12,50%`, HALF_UP and deterministic largest-remainder percentage
closure. Decimal inputs accept comma and dot. Formatting never changes the
stored or submitted precision. Currency symbols and ISO fallback remain shared.
This release adds no exchange rates or currency-specific arithmetic.

Date-only values render as `9 September 2026` in English and an equivalent
Russian textual date. They are not converted through a local timezone.
English date text uses `en-GB`; Russian uses `ru-RU`. Calendar structure remains
Monday-first and ISO weekdays remain machine values. Timestamps retain the
existing browser timezone and 24-hour display. Application-day calculations
continue using the configured application timezone. Native date inputs, file
pickers and browser validation chrome follow the platform language; application
labels and custom decimal validation messages follow the selected language.

## Setup templates and API errors

Fresh setup exposes a separate category-template language, initially matching
the interface when starting fresh. Changing this selection affects only newly
created category names. The interface language remains independent. The optional
API field `category_template_language` accepts `ru` and `en`, defaults to `ru`
for older clients and is validated before setup writes. Category creation still
shares the owner/settings/session setup transaction. Existing and restored names
are never renamed. Categories remain editable user data after creation.

`core/api-error.ts` maps stable server codes into the same catalogs; it is no
longer part of Auth. Known codes take precedence over a localized action-specific
fallback. Network, authentication, throttling and validation errors have safe
fallbacks. Unknown server messages are never displayed verbatim.

Request validation retains HTTP 422 and the `detail` list with `loc`, `type` and
`msg`. The HTTP adapter removes `input` and `ctx`, and emits generic diagnostic
prose instead of reflecting supplied input or custom exception text. Frontend
field labels come from a known allowlist. Existing clients must not rely on
free-form diagnostic prose. Password/ciphertext authentication failures retain
one deliberately non-diagnostic backup message.

The localized restore confirmation is checked in the interface and mapped to the
unchanged published server confirmation string. Switching language does not
rewrite entered confirmation text; it must match the currently displayed phrase.

## Adding and reviewing translations

1. Read this contract and reuse financial terminology. Keys are semantic and
   grouped by feature; they are not the visible source sentence. Do not rename
   a key just because its wording changes.
2. Add or edit messages in `frontend/src/app/i18n/ru.ts` and `en.ts`. Keep the
   exact same keys and named parameter sets. Interpolation is plain text;
   arbitrary HTML and executable translation expressions are unsupported.
3. Call `t(key, parameters)` in the template or in a reactive computation.
   Keep event-created notices in `localizedSignal` with a deferred factory.
   Arrays of translated options must be getters/computations, not startup
   snapshots. Track repeated UI items by stable IDs rather than translated text.
4. Use `plural` with complete forms backed by native Intl rules. Never concatenate
   user-entered content into a translation key. Preserve placeholders when
   changing word order. Static sentence fragments should be consolidated when
   their word order needs to differ between languages.
5. For another community language, add a catalog with the Russian key type,
   register its identifier/catalog/Intl locale in `i18n.ts`, extend the selector,
   completeness checks and locale tests. Keep Russian as fallback. This is
   presentation registration; no financial business code changes are required.
   Additional setup-template languages are a separate optional backend catalog
   addition and must not rename existing records.
6. Run `npm run i18n:check --prefix frontend`, frontend tests, lint, typecheck
   and build. The source-copy check rejects unmigrated Cyrillic literals and
   ordinary untranslated template text, with narrow exceptions for branding,
   native language names, the health endpoint and the published restore command.
   Automated checks supplement human translation review; they cannot certify
   linguistic quality or all accessibility behavior.
7. Verify both languages at desktop and narrow widths, keyboard operation,
   accessible names, long names and large balances. For publication, the owner
   reviews financial terminology and the complete user scenario. Do not expose
   an incomplete community language in the normal selector.

## Boundaries and tradeoffs

Both catalogs ship with the application so language changes are immediate and
work without fetching a translation file. This increases the initial bundle;
current build budgets remain unchanged. Route-level catalog splitting is a
possible measured optimization, not a reason to add an external service.

Only the single-owner browser application is supported. RTL layouts, locale
negotiation, translated stored descriptions, server-side language persistence,
cloud translation, multi-currency and cross-tab synchronization are outside scope.
