# Replacement savings (depreciation accounts)

## Accepted scope

The owner requested purchase replacement savings backed by existing physical
accounts, including accounts already used by ordinary funds. On 2026-09-17 the
owner specified an expected annual inflation input instead of an editable final
price, and redistribution of underfunding only after a month ends. Implementation
was then authorized as a complete bounded vertical slice.

This is a savings plan, not statutory depreciation, a valuation ledger, an
expense schedule or interest earned on a bank account. Registering a purchase
never posts its original expense again.

## Calculation

A purchase records its original cost, purchase month, integer term in months and
expected annual inflation. Its first saving month follows the purchase month;
the last month is purchase month plus the term. A September 2026 purchase over
36 months therefore saves from October 2026 through September 2029 inclusive.

```text
target = cost * (1 + annual_inflation / 100) ** (months / 12)
monthly_plan = max(target - net_savings_before_month, 0) / months_remaining
remaining_this_month = max(monthly_plan - net_contributions_this_month, 0)
```

The compound annual-rate convention is the proposed formula accepted with the
implementation plan. Fractional years use Decimal exponentiation in a local
60-digit context. The derived target is rounded HALF_UP to the existing
NUMERIC(20,4) envelope. Monthly recommendations round down to four places; the
last projected payment receives the exact remainder. Two-place UI rendering is
presentation only and must never replace those exact values.

The current month's recommendation depends only on earlier months. Multiple
contributions are summed; releases subtract from net savings. Underpayments and
overpayments change the following month's recommendation. The target does not
accrue inflation again when payments are missed. Reads reconstruct the schedule
without persisting monthly closing jobs. Skipping several visits/months needs no
catch-up worker and generates no money movements.

Past rows show the recommendation based on facts preceding each month. Future
rows are explicitly provisional: no further contribution in the current month,
then fulfillment of each future recommendation. Actual current-month payments
may change this preview while leaving the current recommendation fixed. Future
recommendations are not added to the existing daily cash forecast or Calendar.

## Financial ownership and lifecycle

Depreciation owns purchases and durable request receipts. Each purchase has one
Funds-owned managed reservation, which may occupy multiple physical accounts.
Funds remains the sole owner of virtual money movements. Managed reservations
are excluded from ordinary fund selectors, percentage previews, dynamic reserve
refills and switching-mode percentage snapshots. Generic fund/operation writes
cannot mutate them. Free money and Forecasting include their actual reservations
through the existing aggregate coverage contracts, exactly once.

A contribution either reserves existing free money on an active account or posts
one physical transfer and reserves its entire amount on the destination. Both
sides and the receipt commit in the same transaction. The request UUID and
payload fingerprint make identical retries idempotent; changed payload reuse or
stale purchase versions fail with a conflict. A contribution cannot exceed the
target or the available free money. A release makes money free on the same
account without recording an expense. Individual account positions cannot be
negative. Ordinary funds cannot borrow these reservations.

Contributions use the current Hermes date/month, not a user-selected repayment
day. The actual transfer retains its real date in Operations. A linked transfer
cannot be edited/deleted independently. Correct a mistaken contribution with an
explicit release and, if needed, an ordinary reverse transfer. Existing facts
remain visible. Archive requires zero savings and preserves history. To use the
savings for replacement, release them, record the actual expense through the
ordinary operation form, and archive the old purchase. These are separate
explicit actions; no automatic spend or replacement purchase is created.

Reaching the target stops further contributions. Expiry with a shortfall is
shown explicitly, never divided by zero or automatically extended. The owner
may still contribute the shortfall after expiry, or release and archive.

## Bounded implementation choices

These technical boundaries are implementation choices, not additional owner
product decisions: positive cost, inflation from 0 to 100 percent inclusive,
term 1 to 600 months, and a target fitting NUMERIC(20,4). Invalid parameters and
overflow are rejected before writes. Purchase month cannot be in the future.
An older purchase is accepted; elapsed months with no recorded contributions are
unfunded. Money already held can be explicitly reserved now, but historical
contributions are not invented or imported. A contribution made in the purchase
month counts as opening savings before the first scheduled month.

Editing original purchase parameters, reopening archived purchases, backdated
contributions, multi-purchase batch allocation, direct fund-aware replacement
expenses, interest, external inflation feeds, automatic transfers, daily forecast
placement and automatic term extension remain outside this slice.

## Consistency and portability

Writes serialize request identity, physical accounts in UUID order, purchase
version and the managed fund. Lists currently lock all existing accounts before
reading purchases and fund facts for one coherent response. This deliberately
simple locking and the complete per-purchase history are scalability debt;
introduce a measured batch read model before large datasets require pagination.

Migration `0017_depreciation` adds the managed flag, purchases and receipts. It
refuses downgrade while purchases exist. Schema-1 backups add optional records
and default old funds to unmanaged. New code restores older backups; old code
rejects the new fields rather than silently discarding savings. Backup validation
checks one-to-one purchase/reservation ownership, derived targets, zero allocation
percentages, receipt/event links, event signs and target capacity, in addition to
existing coverage and ledger rules. JSON and protected envelopes share this data
model and atomic restoration.
