# ADR 0006: Minimum balance buffer for baseline forecasts

- Status: accepted; not yet implemented
- Date: 2026-10-24
- Decision owner: project owner

## Context

The baseline forecast currently recommends an amount that can be spent without
the projected balance falling below zero. A positive forecast minimum therefore
appears fully spendable even when the owner wants to retain a personal cash
buffer. Virtual-fund reserves are already a separate model and cannot express
this general minimum without changing allocations.

The decision must preserve the distinction between factual balances, planned
events, virtual-fund reserves, and a read-only spending recommendation.

## Decision

Hermes will introduce one persisted, exact-decimal, non-negative **minimum
balance buffer** in Application Settings. Its default is `0.00`; zero disables
the additional buffer. The value is expressed in the application's base
currency and is included in backup and restore.

The setting applies to every baseline forecast scope and to both free-money and
all-money views. It changes neither the forecast series nor the displayed raw
minimum, plans, ledger facts, or virtual-fund allocations. For a forecast whose
minimum includes the current starting balance and all projected daily closings,
the safe-spend recommendation is:

```
max(0, forecast minimum balance - minimum balance buffer)
```

When no negative forecast balance exists, a forecast that falls below a positive
buffer reports the earliest buffer breach, including an immediate breach when
the current balance is already below the buffer. The chart gives the buffer a
separate labelled boundary. If the forecast contains any cash gap, the cash-gap
risk has priority and is the only risk warning shown; Hermes does not duplicate
the buffer breach.

The setting is edited on the Settings screen. Forecast shows the active buffer
and links to Settings rather than providing a second editing surface. Input
accepts comma or dot decimal separators and validates an exact non-negative
amount; rendered values follow the shared financial presentation contract.

## Alternatives considered

- **Treat the buffer as a virtual fund reserve.** Rejected because a general
  spending boundary must not alter fund allocation or imply that the money has
  a fund purpose.
- **Keep the zero-only rule.** Rejected because it cannot express the owner's
  deliberate cash reserve.
- **Store one buffer per account or per displayed forecast.** Rejected in favor
  of a single owner-level policy that remains consistent across scopes and
  devices.
- **Show buffer and cash-gap warnings together.** Rejected because a cash gap
  is the more urgent and less ambiguous condition.

## Consequences

Implementation needs a Settings-owned persistent field, public Settings
contract, backup/restore compatibility policy, exact-decimal validation, and
one consistent Forecasting read. It also needs focused tests for zero,
positive, current-day, future breach, cash-gap priority, all scopes and both
balance modes. This ADR authorizes the policy; it does not claim an implemented
schema, API, UI, migration, or verified release.
