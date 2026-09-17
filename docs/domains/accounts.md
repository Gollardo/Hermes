# Accounts

## Owner-confirmed rules

The first account types are `cash`, `debit` and `savings`. An account balance is
not an ordinary editable field: the journal of financial operations and related
money movements is the source of truth. An initial balance is posted as a
`balance_adjustment` operation.

For a concrete account, the sum of virtual funds assigned to it must not exceed
its available physical balance.

## Terms and invariants

- **Physical balance**: sum of posted physical money movements for an account.
- **Available physical balance**: in the current release, the non-negative
  physical balance eligible to cover funds. Pending transactions and overdraft
  may refine this definition only through a later explicit design.
- **Free money**: available physical balance not virtually assigned to funds.

Balances are calculated with exact decimal values: Python `Decimal`, PostgreSQL
`NUMERIC`, and decimal strings at JSON boundaries where numeric parsing could
lose precision. Binary `float` is forbidden.

## Release 0.1.0-alpha.2 behavior

- Accounts contain type, trimmed name, optional description and lifecycle timestamps.
- The supported amount envelope is `NUMERIC(20,4)`; JSON writes and reads use decimal strings.
- Creating the first account locks the singleton base currency in the same transaction.
- A non-zero initial balance creates one `balance_adjustment` and one account movement.
- A zero initial balance creates no synthetic zero movement.
- Initial and resulting physical balances are non-negative in the current
  release. Overdraft semantics require a later explicit design.
- Edit does not accept a balance field. Balance is always the sum of movements.
- Archive and restore preserve ledger history. Physical deletion is allowed only without movements.
- Archiving is allowed while physical history or fund positions exist. Archived
  accounts remain readable and participate in combined balances/forecasting,
  but new operations require active references; an edit may retain its existing
  archived account reference.
- Physical deletion locks the account before checking history, so a concurrent
  posting either observes a deleted account or commits first and makes deletion
  return the normal history conflict.
- Initial-balance dates use the configured application timezone, not the host or
  database-session timezone.

## Boundary

Accounts owns account identity, lifecycle and type rules. Operations owns posted
movements. Accounts may expose a balance read contract, but it must not allow a
caller to overwrite the derived balance.

## Open questions

- Currency-specific precision and rounding beyond the alpha-wide four-decimal envelope.
- A future account-specific overdraft model; it is not enabled by the current
  non-negative policy.
- Whether the implemented archive-while-preserving ledger/fund positions policy
  should become the long-term account-closing model.
- Treatment of pending bank transactions, which are not in current scope.

## Replacement savings

Managed replacement reservations share the Funds coverage ledger. Free money
subtracts ordinary funds, replacement savings and dynamic reserves once each.
The per-account summary exposes these purposes separately; no new physical
account type or editable balance is introduced.
