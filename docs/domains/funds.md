# Virtual funds

## Meaning and ownership

A fund is a virtual purpose assigned to real money, never a bank account. One
fund may span physical accounts. Funds owns definitions, percentages, events
and per-account virtual movements; Operations owns physical movements. The
posting model is recorded in [ADR 0002](../decisions/0002-virtual-fund-ledger.md).

## Implemented model through 0.5.0

- A fund has a name, optional description, optional positive target amount,
  exact allocation percentage, lifecycle state and optimistic version. A target
  is planning metadata and never changes ledger balance.
- Allocation has a global manual or dynamic mode. Manual percentages total at
  most 100%. Changing a percentage or mode never moves existing money.
- Fund totals and positions are sums of `NUMERIC(20,4)` movements; there is no
  mutable authoritative balance.
- Account coverage is `physical = ordinary funds + replacement savings + reserve + free`, with non-negative
  individual fund positions and a non-negative reserve on every account.
- Explicit allocation reserves a selected part of one account's free balance;
  the remainder stays free.
- Fund creation may atomically reserve an explicitly entered amount from one
  account for the newly created fund only. It does not invoke percentage
  distribution and rolls the definition back if allocation is invalid.
- A convenience command may atomically transfer physical money to another
  account and either explicitly distribute the transferred amount across active
  funds by their configured percentages or assign its complete amount to one
  active fund. It produces one ordinary transfer plus one causally linked
  allocation event and rolls both back on failure. Deleting the transfer also
  deletes that allocation event atomically. The ordinary operation editor
  rejects a change to this composed transfer because it cannot represent its
  allocation; replacement uses the composed command.
- An expense may consume one fund completely or use free money. A transfer may
  carry one virtual part no greater than its physical amount.
- Virtual redistribution moves one fund between accounts without physical
  movements. Both transfer forms preserve the total fund balance.
- A fund-to-fund transfer moves a virtual position between two different funds
  on the same physical account. It preserves account balance, account reserved
  total and the total held by all funds.
- Create, edit and delete of fund-linked financial operations replace both
  ledgers atomically and recheck the resulting state.
- History includes allocations, redistributions, fund expenses and transfers.
- New actions use active physical accounts; operation entry exposes a fund only
  when it has a positive position on the selected source account.

## Allocation modes and rounding

Manual mode preserves the original policy. For every active fund independently:

```text
allocation = round_down(amount * percentage / 100, 4 decimal places)
```

Fund order cannot affect the result. Percentage, rounding and manual
remainders stay free. Manual values must be non-negative, unique per fund and
total no more than both the selected amount and current free balance. Binary
floating point is rejected at API boundaries.

In dynamic mode, a manually adjusted preview is also rejected if any resulting
fund position would exceed that fund's target. The rejected request creates
neither fund nor reserve movements.

Dynamic mode requires a positive target on every non-archived fund. Before
each distribution, active funds are those with `balance < target`; archived or
filled funds receive zero. For `N` active funds:

```text
relative_gap_i = (target_i - balance_i) / target_i
base = min(5, 100 / N)
percent_i = base + (100 - N * base) * relative_gap_i / sum(relative_gap)
```

Percentages use four decimal places and a deterministic largest-remainder
correction in UUID order so active percentages total exactly 100. Allocation is
iterated in the same transaction: each fund is capped at its target and the
remainder is recalculated among funds that still have capacity. Any final
excess enters the fund reserve on the receiving account, including when no fund
exists or every goal is full.
Funds at the same completion percentage receive equal dynamic shares even when
their target amounts differ. While `N < 20`, a less-complete fund receives more
of the non-base dynamic pool; target size by itself is not an implicit priority.
At `N >= 20`, `base = 100 / N` consumes the complete percentage, so every active
fund receives the same share apart from deterministic `0.0001` closure units.
The next preview, transfer or forecast event recomputes from current/projected
balances. Direct replenishment, spending, archival and restoration therefore
affect the next calculation without a stored percentage cache.

The reserve exists only for dynamic allocation. It is a separate ledger, not a
system fund: it has no goal, percentage or fund lifecycle. When any fund becomes
incomplete, reserves from all accounts are consumed automatically according to
the current dynamic percentages without moving physical cash between accounts.
An operation-caused refill is linked to that operation, so editing or deleting
it reverses the refill in the same database transaction. Lowering a goal never
moves an existing excess into reserve. The only manual reserve action releases
an exact positive amount to free money on the same account; manual
reserve-to-fund posting is unavailable. Manual mode keeps existing reserve
balances frozen until dynamic mode is restored.

Switching dynamic to manual copies the current effective percentages into the
manual percentage fields atomically; filled and archived funds are stored as
zero. Switching manual to dynamic validates all non-archived targets first.

### Plain-language release behavior

- In manual mode each fund amount is rounded down independently to four decimal
  places. For example, distributing `100.0000` between three funds at
  `33.3333%` gives `33.3333` to each and leaves `0.0001` free; Hermes never
  hides or assigns that remainder implicitly.
- In dynamic mode the deterministic largest-remainder calculation distributes
  every `0.0001`, so the effective percentages and allocated amount total
  exactly 100% of the input while eligible funds exist.
- A fund can be archived only after its total balance reaches zero. Reserved
  money must first be spent or moved explicitly; archival never releases or
  relocates it silently. An archived fund remains readable in history and does
  not receive new allocations until explicitly restored.

## Concurrency and lifecycle

Account rows and then fund rows are locked in UUID order before
coverage-dependent writes. Concurrent commands cannot overreserve one account
or fund position. Definition writes share a transaction advisory lock, so the
percentage limit also holds under concurrency.

The archive policy permits archive only at zero total balance. Restore is
explicit and version-checked. An archived fund is excluded from dynamic
calculation; restoration re-includes it when it is below target and, in dynamic
mode, requires a target. Editing or deleting
an older linked operation cannot make an archived fund non-zero. Reserved money
is never silently released or moved.

## Deliberately outside 0.5.0

- automatic allocation while posting income;
- per-transfer mode overrides or custom dynamic formulas;
- splitting one expense or transfer across several funds;
- target date, icons, colours or gamification;
- batch allocation across multiple accounts;
- fund overflow or inflation buffers;
- manual reserve-to-fund allocation or cross-account reserve transfer;
- edit/delete lifecycle for explicit allocation and redistribution facts;
- immutable audit history and bulk actions;
- currency-specific precision and exchange rates.

## Explicit release to free money (unreleased)

The Funds screen can release a positive exact amount from one active fund's
position on one active account. Keeping it on that account creates one negative
`fund_release` virtual movement and no physical operation. Selecting another
active account atomically releases the source position and posts an ordinary
physical transfer; the receiving money is free, not assigned to the fund.
This records a completed fact, never initiates a bank transfer, and cannot be
future-dated. It creates neither income nor an additional purchase expense.

`POST /funds/releases` accepts `request_id`, `fund_id`, `account_id`, optional
`destination_account_id`, positive exact `amount`, `occurred_on`, and optional
`description`. An equal source and destination is normalized to no transfer.
The request UUID becomes the release event ID. Repeating the same normalized
request returns the existing result; reusing its ID for different fields
conflicts. This replay guarantee lasts while the fact exists, including after
backup/restore; deletion is not a permanent idempotency tombstone.

Account locks precede fund locks. Coverage, active references and the source
fund position are checked in the same transaction as both ledgers. In dynamic
mode the existing automatic reserve refill runs afterwards: reserve money can
refill incomplete funds without changing the newly freed money. The UI discloses
this, because the final fund balance may decrease by less than the release.
A refill caused by a transfer remains causally linked to that transfer.

Same-account releases follow the existing immutable explicit-event lifecycle.
A release with transfer links its event to the operation. Ordinary editing is
rejected; change it by deleting and recreating the whole composed action.
Deletion reverses the release, physical transfer and dependent reserve refill
atomically, and fails if resulting coverage, non-negative positions, or the
zero-balance invariant of an archived fund would be violated.

This slice does not link a release to a purchase, prove that a reimbursement is
unique per purchase, split it across funds, create plans, or initiate payments.

## Managed replacement reservations

[Replacement savings](depreciation.md) uses managed fund positions with zero
percentage and a derived target. They participate in physical coverage and free
balance exactly once, but not in ordinary lists, manual/dynamic distribution or
reserve refills. Their writes belong to the explicit managed posting contract.
Summary responses separate replacement totals and per-account replacement
positions from ordinary fund balances. Generic fund operations cannot change
managed definitions or their positions.
