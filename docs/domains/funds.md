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
- Account coverage is `physical = funds + reserve + free`, with non-negative
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


## Oracle source snapshot

Funds exposes `projection_funds` for active definitions and balances inside
Oracle's repeatable-read, read-only transaction. Ordinary list/posting callers
retain the existing locking defaults. Oracle reuses the public manual/dynamic
allocation calculators; it adds no virtual movements or automatic expense funding.
