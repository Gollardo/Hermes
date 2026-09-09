# Application settings

## Ownership and current fields

The `settings` module owns persisted owner preferences: the base currency,
IANA timezone, an optional default account and the global fund allocation mode.
Runtime deployment configuration remains in
`app.core.config` and environment variables.

Setup creates exactly one settings row in the same transaction as the owner
credential. Authenticated owners can read settings, change the timezone and
change the base currency only while it is unlocked.

## Invariants

- There is exactly one settings row with singleton identity `1` after setup.
- Currency is normalized to an uppercase, three-letter ISO 4217-style code.
  This release validates code shape, not membership in an external currency
  registry.
- Timezone must resolve through the runtime IANA timezone database.
- The base currency becomes immutable once monetary/account data exists. The
  settings module exposes `lock_base_currency(session)` as its public contract;
  the account application use case calls it in the same transaction as the first
  account and optional initial-balance movement.
- Currency-independent category writes do not lock the base currency.
- Locking is idempotent. Changing only the timezone remains valid after the
  currency lock.
- Currency changes and the first financial lock take a row-level lock on the
  singleton settings record, so concurrent transactions cannot change the
  currency after a financial write establishes the lock.
- A default account must reference an active account. Archiving clears the
  preference in the same transaction; deletion is protected by both application
  cleanup and a nullable foreign key with `ON DELETE SET NULL`. It is only a
  mutable convenience default for new income and expense forms, never a posting
  rule. Settings updates and account archival/deletion use the common lock order
  `Settings → Accounts`.
- Fund allocation mode is `manual` or `dynamic`. Enabling dynamic mode requires
  a positive target for every non-archived fund. Returning to manual mode
  snapshots current effective percentages, including zero for filled and
  archived funds, in the same transaction. Dynamic effective percentages are
  derived from relative unfilled target progress rather than persisted as
  another setting. The application use case observes the common
  `Settings → Funds` lock order.

## Explicit assumptions

- A single base currency is sufficient until per-account currency and
  conversion-aware reporting are designed.
- The interface uses a familiar currency symbol where one is known and falls
  back to the currency code. Currency-specific decimal scales and exchange
  rates remain outside this release.
- Browser timezone suggestions are convenience only; backend validation is
  authoritative.

## Browser language preference

RU/EN interface language is browser-local presentation state, not a persisted
Application Settings field. It changes neither the currency nor timezone locks.
No settings migration or language backup field is introduced. See the
[internationalization contract](../ui-ux/internationalization.md).
