# Financial operations

## Domain vocabulary and implemented types

`income`, `expense`, `transfer`, `balance_adjustment`, `loan_disbursement`,
`loan_payment`, `debt_issuance` and `debt_repayment`.

The current `0.5.0` operation schema and API implement only `income`, `expense`,
`transfer` and `balance_adjustment`. The loan/debt names are owner-confirmed
future vocabulary; they are not accepted enum values until those domains and
their posting rules are designed.

Operations may be edited and deleted unless another accepted domain fact must
retain its identity. In beta.1, an operation linked from a confirmed expected
occurrence cannot be deleted independently. Every allowed change to one
financial operation—including its physical and virtual consequences—must
complete atomically in one database transaction.

For the first ordinary-operation model:

- `income` and `expense` require a category;
- the user records the calendar date when the financial fact occurred;
- exact time is not collected;
- ordinary operations do not require a separate payee field in the MVP;
- description is optional in the alpha implementation; long-term owner review
  remains open.

## Ledger semantics

An operation is the user-meaningful fact; associated money movements are its
effect on accounts. Account balances are derived from those posted movements.
Transfers decrease one physical account and increase another. An adjustment is
explicit history, including initial balance, rather than direct balance mutation.

If a fund participates, its virtual movement shares the operation transaction.
In `0.1.0-alpha.4`, an expense may consume one complete fund amount and a
transfer may carry one explicitly smaller or equal virtual part. Create, replace
and delete recheck both physical and virtual resulting balances through Funds'
public posting contract.
The ordinary posting flow is documented in [data flows](../architecture/data-flow.md).

## Boundary and consistency

Operations owns the journal and posted physical movements. It validates public
references to accounts and categories. Other modules request posting through an
operations-owned command or shared use case; they do not insert ledger rows
directly.

Scheduling confirmation uses that public posting command and writes the
expected-occurrence link in the same transaction. A retry receives the existing
link. Operations does not read Scheduling's private tables; a restrictive
named foreign key protects the confirmed link on deletion. Only violation of
that exact constraint is translated to the linked-operation domain conflict;
unrelated integrity failures are not hidden behind it.

The ability to edit/delete is owner-confirmed. The current implementation keeps
only the latest operation version: an edit replaces its movements and a delete
removes the operation. The owner confirmed on 2026-08-18 that a separate
immutable history of before/after values and deletions is not required for the
current single-owner product. It may be reconsidered only if the product scope
or reconciliation requirements change.

## Release 0.1.0-alpha.2 foundation

At that release, only `balance_adjustment` posting for a non-zero initial
account balance was implemented. Account creation, currency locking, operation
creation and movement creation shared one request transaction. General
income/expense/transfer commands were added in `0.1.0-alpha.3`.

## Release 0.1.0-alpha.3 posting model

The separately reviewed posting model is recorded in
[ADR 0001](../decisions/0001-financial-posting-model.md). Income and expense
have one signed account movement because their counter-side is outside the
modelled account universe. A transfer has equal opposite movements and is the
only operation required to net to zero across accounts. Adjustments contain one
signed ledger delta and a visible reason; the UI asks for the expected balance
and calculates that delta exactly before posting.

The financial fact uses a calendar `occurred_on` date. Creation timestamp and
identifier provide stable ordering within the date but do not add user-visible
financial time. Integer optimistic versions reject lost edits and deletes.
Defaults and migration from the old timestamp resolve calendar dates through the
configured application timezone.

The public create and replace API rejects a date later than application today
with `future_operation_requires_plan`. The operations posting contract remains
available to approved cross-module use cases; Scheduling uses it only while
applying a one-off plan on application today or retaining the established
recurring-confirmation behavior.

Journal totals are calculated over the complete filtered selection, not the
visible page. Without an account filter they represent the net change across all
modelled accounts, so transfers contribute zero. With an account filter they sum
that account's matching movements.

Filtering by a root category includes its direct children; filtering by a leaf
uses that leaf only. The current-month category summary rolls child operations
up to their root, separates income from expense, uses absolute category amounts
and orders roots by amount before name. This read model powers dashboard
drill-down without giving the dashboard access to private ledger tables.

For the current release, an operation mutation may not leave any affected physical
account below zero. Affected accounts are locked in deterministic order before
the ledger-derived post-mutation balances are checked. The owner confirmed this
rule on 2026-08-18. Overdraft remains a separately designed future capability.

## Remaining open questions

- Reconciliation requirements if future integrations change the product scope.
- Rounding policy once currency precision is chosen.
- Account-specific overdraft policy beyond the current non-negative rule.

## Statement provenance

Reviewed statement facts use the same posting, fund coverage, exact amount and
non-negative balance rules. Dates are explicitly selected by the user and may
not be future facts. Linking a statement row to an existing fact verifies its
version and reviewed financial fields without reposting. Import receipts remain
after allowed edits/deletions; they never override the journal or recreate a
deleted fact. Confirmed-plan deletion protection remains unchanged.
