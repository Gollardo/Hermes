# Funds

## Status

The owner approved the implemented `0.4.0` composition on 2026-08-18 as the
first-public-release baseline. A visual design system has not been formalized,
while posting, rounding, and archive rules are recorded in ADR 0002 as the
owner-confirmed current-release policy.

After owner review on 2026-08-12, the screen uses explicit actions: “Reserve
from account”, “Transfer and allocate”, and “Move assignment between accounts”.
The former term “fund redistribution” is not used without explaining the
physical effect.

The visual refinement on 2026-08-17 preserves these workflows while
strengthening hierarchy: primary monetary totals are separated from secondary
percentages, rare transfers are disclosed on request, and funds appear in one
dense aligned list instead of nested cards.

## Screen goal

Show what real money is intended for, where it is physically held, and how much
remains free. The owner must understand that a fund is a virtual assignment,
not another bank account.

## Primary user jobs

- see the total in all funds and total free money;
- see the dynamic reserve separately, with its physical-account breakdown;
- check each fund's state;
- see a fund target, amount, progress percentage, and combined target progress;
- understand the fund's physical account breakdown;
- create, edit, or archive a fund;
- reserve a specific free amount immediately only when creating a new fund;
- configure allocation percentages;
- see the selected manual or dynamic mode and current calculated percentages;
- allocate a selected amount with a preview;
- manually adjust a proposed allocation;
- transfer an amount from one physical account to one existing active fund on
  another account without changing its percentage for future allocation;
- transfer money from another physical account and allocate it on the
  destination account by active-fund percentages in the same transaction;
- open virtual-movement history;
- move an assignment between two funds on one physical account;
- understand why an allocation or expense is unavailable.

## Important information

### Global summary

- combined compatible physical balance;
- total reserved in funds;
- total free;
- sum of active-fund percentages and unallocated share;
- warning when a verifiable invariant cannot be satisfied.

### Fund list

For each fund:

- name and optional short description;
- current total virtual amount;
- optional target amount, exact completion percentage, and progress bar;
- percentage for future explicit allocation;
- account breakdown or an affordance to reveal it;
- lifecycle state;
- one expected contextual action.

### Physical coverage

The screen supports two perspectives:

- fund → which accounts hold its portions;
- account → physical, in funds, in reserve, and free amounts.

An expandable list may serve a small number of entities. Many funds and
accounts may require a matrix or table view; decide after measuring real data.

## Secondary information

- allocation and fund-expense history;
- date of the latest movement;
- archived funds in a separate mode;
- a target date remains outside the current scope; target amount was confirmed
  on 2026-08-14;
- optional decorative fund icon or color for scanning, never a required field.

## Primary actions

- create a fund;
- edit name, description, and percentage;
- open details or history;
- allocate an arbitrary incoming amount;
- adjust allocation preview before commit;
- transfer an amount to one selected fund without using the percentage preview;
- redistribute the virtual portion between accounts within the approved model;
- initiate an expense from a fund through the shared operation form;
- archive or restore after balance handling is satisfied.

## Allocation flow

1. The owner selects an amount and eligible physical source.
2. The system calculates allocation by active percentages using exact decimal
   arithmetic.
3. Preview shows each fund amount, remaining free money, and rounding remainder.
4. The owner may change values within valid bounds.
5. After manual adjustment, totals recalculate with exact decimal arithmetic;
   the actually selected amount and ending free balance appear before saving.
6. Allocation commits atomically or changes nothing.

In dynamic mode, valid bounds include each fund's remaining target capacity;
the server rejects stale or edited allocations that would overflow a goal.

The owner may instead choose one existing active fund when moving money between
physical accounts. The command posts one physical transfer and one allocation
of its whole amount on the destination account in the same transaction. It
leaves configured or calculated percentages unchanged and does not require a
percentage preview. The same source-balance and dynamic target-capacity checks
apply, including the server-side check at commit.

Changing account or source amount invalidates the old preview. New allocations
and redistributions offer only active physical accounts. Amounts use the base
application currency; history is server-paginated.

Changing percentages alone must not visually imply redistribution of money
already accumulated unless that behavior is separately confirmed.

## Possible states

### No funds

The empty state explains the model with a short numerical example: real money
stays in an account, while a fund only assigns part of it. The primary action is
“Create fund”.

### Funds exist with zero balances

Show percentages and an allocation action. A zero amount is not an error.

### Percentages total less than 100%

Label the remaining share as free. This is valid, not a warning.

### Percentages total 100%

Preview shows no percentage remainder but does not claim that all current
physical money is already in funds.

### Dynamic mode

Every non-archived fund requires a target. The list shows the current calculated
percentage and explains zero for a filled or archived fund. The dynamic pool is
weighted by each goal's relative unfilled share, so equal completion levels
receive equal shares regardless of target size. When 20 or more funds are
active, the guaranteed equal base consumes the complete percentage and the UI
must explain that relative progress no longer differentiates them. Percentage
is not editable in the fund form. Allocations are capped at goals and
recalculated until no eligible capacity remains. With no incomplete funds, the
amount enters a separately labelled reserve on the receiving account instead
of appearing free or failing. The reserve section is separate from the fund
list, discloses account detail, and offers only “Return to free money”; the user
cannot choose a fund for reserve consumption. History explains automatic refill
from reserves across accounts. Archiving excludes a fund; restoring it returns
it to the next calculation.

### Attempt to exceed 100%

Saving is blocked before the request and checked again by the server. The
interface shows the available percentage derived from exact values in the
shared two-place UI format. Domain values are never silently normalized.

### Insufficient physical coverage

Show the specific account, physically available amount, already reserved
amount, and required amount. The solution does not move money between accounts
automatically.

### Fund distributed across many accounts

The total remains primary, with its physical breakdown nearby. The portions
must visibly sum to the total.

### Archiving a fund with a balance

Archiving is blocked until total balance reaches zero. The interface neither
releases nor moves an assignment implicitly.

### Save failure or conflict

Preserve preview and manual changes. After current state arrives, show which
value caused the conflict.

## UX failures to avoid

- depicting a fund as a card or independent physical account;
- one progress bar without amount, percentage, and physical breakdown;
- mixing the allocation percentage for new money with the current-balance
  share;
- automatically changing existing amounts when a percentage changes;
- hiding the rounding remainder;
- normalizing percentages above 100% automatically;
- an expense from a fund that silently consumes free money;
- archiving with implicit loss of the remaining assignment;
- excessive savings gamification or judgment of the owner;
- using fund color as its only identifier.

## Questions for prototype validation

- Does the owner think fund-first or account-first?
- Is a matrix needed at the expected number of accounts and funds?
- Which matters more in the list: current amount or allocation percentage?
- Is a target date needed in addition to target amount?
- How should remaining balance be handled before archiving?

## Multilingual presentation

The implemented RU/EN presentation follows the shared
[internationalization contract](../internationalization.md). Language changes
update screen copy and accessible labels while preserving financial semantics,
user-entered data, dates, selected context and exact monetary payloads.
