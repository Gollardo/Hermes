# Operation entry

## Status

The owner confirmed the primary UX focus on 2026-08-02. After owner review on
2026-08-12, the composer moved from a permanent journal column to a modal layer.
It uses the ADR 0001 alpha model: negative balance is blocked, a version
conflict never overwrites silently, the current product does not require a
separate immutable edit history, and currency-specific rounding remains open.
No type is selected initially, the primary action is enabled only for a
complete form, and the default date comes from the server's application-today
contract in the configured application timezone.

For a fund-aware expense or transfer, available funds depend on the selected
source account: the interface shows the fund position on that account rather
than the fund's combined balance. An archived fund remains visible when editing
a linked operation, but the result must still preserve the archive invariant.

The modal opens from the journal header or contextual editing and does not
reduce journal width while browsing. The primary action is a keyboard-accessible
dropdown of four types; selecting one immediately opens the matching composer.
For new income or expense, the configured active default account is prefilled
but remains editable.

The current composer uses the same geometry for native and searchable controls,
a two-column grouping of related fields on wide screens, and one column on
narrow screens. The title and action footer remain visible while a long
operation form scrolls. Optional description appears on request; the required
adjustment reason is visible immediately.

## Screen goal

Record one or a series of financial facts quickly and pleasantly while showing
their account and, where relevant, fund effects in advance.

The owner approved the current modal for ordinary operations on 2026-08-18 as
the release baseline. A side panel may be explored later only as an alternative,
not a first-public-release requirement.

## Primary user jobs

- select operation type;
- for income or expense, choose the required category first;
- enter the exact amount;
- specify the affected account or account pair;
- for an expense, choose a fund source or free money;
- verify the fact date and optional description;
- understand the total effect and save;
- move quickly to the next operation during batch manual entry.

## Model by type

### Income

Required data: amount, destination account, date, and income category under the
approved model. Description remains available, but whether it must be required
is a separate decision.

After funds exist, income is not allocated automatically without an explicit
owner-confirmed rule. A separate “Save and allocate” action may be proposed if
that workflow is approved.

### Expense

Required data: amount, account, date, and expense category. The coverage source
is explicit: free money or a specific fund position on that account.

Ordinary MVP income and expense do not require a separate payee. Counterparty
remains a concept for outgoing debts and must not be prematurely added to every
operation.

### Transfer

Required data: amount, source account, destination account, and date. Category
normally does not apply unless the domain later decides otherwise. Source and
destination cannot match.

When a virtual fund portion moves, the form shows it separately and does not
allow the virtual movement to look like another physical transfer.

### Adjustment

An adjustment brings the ledger-derived balance to a known fact. The form shows
current balance, new expected balance, calculated difference, and reason. The
owner neither edits an account balance field nor enters a signed delta; the
composer calculates the journal movement from the expected balance exactly.

### Future date

For income, expense and transfer, a date later than server-provided application
today changes the primary action to “Schedule”. The composer explains that the
event enters Calendar and forecast while the balance remains unchanged until
application. It reuses the same exact-money fields for plan editing. A balance
adjustment cannot be scheduled.

Opening an actionable recurring occurrence uses the same composer in a
confirmation mode. Its operation fields are prefilled from the occurrence and
remain editable, while the plan date is shown separately and the fact date is
the current Hermes application day. Submission confirms and posts in one
transaction; it does not edit the recurring rule or its sibling occurrences.

## Important information

- operation type as an explicit selected state;
- amount with currency context and no ambiguous sign; addition and subtraction
  may be entered as one exact expression and are resolved before submission;
- account or transfer direction;
- fact date in the application timezone with no separate time;
- category for income or expense;
- fund or free money when funds participate;
- concise effect summary before saving;
- errors tied to a field and financial consequence.

## Secondary information

- description or note;
- link to an expected event;
- change history under any future audit approach;
- templates, duplication, or additional saved defaults only after a separate
  backlog decision after `0.4.0`;
- technical operation identifier in detail or debug context, not the primary
  form.

## Interaction order

1. Open from a global or contextual action.
2. Select a type directly in the quick-create menu.
3. For income or expense, select the required category: purpose or source.
4. Enter amount.
5. Select account and verify the visible fact date.
6. Progressively disclose description and additional fields.
7. Validate inline as fields are completed without premature errors before
   first interaction.
8. Show an effect summary without a separate confirmation for ordinary
   creation.
9. Save atomically with an unambiguous result.
10. For batch entry, open the next composer with only safe preserved context.

## Primary actions

- save;
- save and add another where it accelerates batch entry;
- cancel without unexpectedly losing a substantial draft;
- switch type before dependent input, or after a clear warning;
- open the full form;
- while editing, delete with a recalculation explanation;
- from an expected event, confirm with prefilled data.

## Defaults and acceleration

- Current date may be the default but remains visible.
- An account or fund from page context may be preselected but never hidden.
- The last category or a history-based suggestion is acceptable only as an
  editable hint, not opaque automatic application.
- Creating a category inside a financial form requires caution: it accelerates
  first entry but complicates the category tree and error handling.
- Keyboard shortcut and correct tab order are mandatory in a desktop prototype.
- A draft protects against accidental close; its retention policy must consider
  financial-data sensitivity.
- Future import uses a separate preview and confirmation pipeline, but its result
  enters the same understandable journal. Mapping fields do not complicate the
  manual composer.

## Possible states

### Initial

Type and defaults are visible. The primary action remains disabled until enough
data exists, but the interface shows no red errors before interaction.

### Incomplete data

State exactly what remains. Move focus to the first problematic field only
after a save attempt.

### Insufficient balance

The backend blocks a mutation that would leave an affected account below zero,
and the UI shows a localized explanation. This is a conservative alpha policy,
not the final overdraft model.

### Insufficient fund money

Show the available virtual amount on the selected account and alternatives:
reduce the expense from the fund, choose free money, or change allocation when
the domain permits it. Never silently take the difference from another source.

### Archived reference

An old operation continues to show its archived account or category. Archived
entities are unavailable for creation. During editing, the existing archived
reference remains visible with an “Archived” label and may be preserved, but a
different archived entity cannot be selected.

### Edit conflict

Input is not lost. State that source data changed, show the current effect, and
offer an intentional retry.

### Saving

The primary action prevents duplicate submission. Success appears only after a
confirmed commit; failure neither closes nor clears the form.

### Success

Show the created operation and effect. Close the layer for ordinary single
entry; “add another” preserves only approved safe defaults.

### Deleting or editing an operation with a fund

Confirmation explains that physical and virtual movements change atomically and
which current balances will be recalculated.

## UX failures to avoid

- one signed amount instead of an explicit type;
- two independent saves for physical and fund portions;
- automatic income allocation without preview and an approved rule;
- hidden transfer source or destination;
- an invisible date or account default;
- clearing the form after a failed request;
- a success toast before commit;
- every possible field in one long form;
- mandatory modal confirmation for every ordinary operation;
- creating an archived category from an old value;
- money input through binary `float`, or formatting that changes entered
  precision;
- a keyboard shortcut with no visible mouse or touch action.

## Questions for prototype validation

- Should a type have a default, or should income and expense be equally
  explicit choices?
- Must description be required?
- Should one adaptive overlay appear as a modal or side panel depending on
  context and viewport?
- Should a draft survive reload, logout, and device changes, and how long should
  it persist?
- How often is an expense linked to a fund, and does fund selection belong in
  the primary form layer?

## Multilingual presentation

The implemented RU/EN presentation follows the shared
[internationalization contract](../internationalization.md). Language changes
update screen copy and accessible labels while preserving financial semantics,
user-entered data, dates, selected context and exact monetary payloads.
