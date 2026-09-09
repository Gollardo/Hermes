# Calendar and recurring operations direction

## Status

Owner-confirmed beta.1 scope implemented using the existing preliminary visual
direction. This is not approval of a final design system.

## User job

The owner needs to see what is expected, distinguish it from posted money and
resolve an occurrence with one deliberate action. The screen combines the
monthly context, an action-oriented upcoming list and recurring-rule management.

## Information hierarchy

1. Explanation that expected events do not affect actual balances.
2. Only today's and overdue actionable occurrences with confirm, date-specific
   postpone and cancel actions; future items remain in the calendar grid.
3. Month navigation and visible account/type filters.
4. Seven-column monthly grid with signed daily net summaries.
5. Rule list and create/edit form.

The attention list is the primary action surface and remains before the dense
monthly grid at every width. The calendar uses an internally scrollable grid on
narrow screens instead of expanding the document. It never includes future
events merely because they are within the next 30 days.

## States and actions

- `pending` and `postponed` expose quick actions.
- A one-off plan is visibly labelled “One-off”, never presented as a recurrence
  rule, and offers Apply today, edit, move and cancel. Apply today warns that
  an early plan posts today rather than its planned date.
- `confirmed` remains visible and links to the exact posted operation; route
  navigation resets scroll so the linked-fact context is visible immediately.
- `cancelled` remains visible but visually secondary.
- Overdue is communicated by text and boundary treatment, never by color alone.
- A calendar day displays one signed net amount for pending or postponed income
  and expense occurrences; confirmed snapshots remain visible in day details
  but do not enter the planned aggregate. A zero net amount remains blank.
  Transfers do not enter that aggregate because they are neutral for the
  all-account total.
- A date with events and its daily amount open the complete day list. The list
  retains every occurrence title, type, status and amount; color and
  strike-through remain supplementary signals there.
- Opening an actionable recurring occurrence starts a reviewed confirmation in
  the established operation composer instead of editing its rule. The composer
  allows the selected occurrence's operation fields to change, states both the
  plan date and application-today fact date, and keeps rule editing separate.
- A daily amount is a restrained bordered control, not an occurrence card.
  Negative daily amounts use the existing soft risk surface with a textual
  minus sign; a day with overdue occurrences also states their count in text
  beside the aggregate.
- A failed confirmation keeps the occurrence and entered postpone date visible.
- A rule may expose an explicit “shift following events” option. Before a
  postpone action, the interface states the signed day delta and that only
  untouched later events move; the result reports shifted and preserved counts.
- An automatically cancelled dated exception protected during a series shift
  remains cancelled and carries a visible preservation explanation; it is not
  presented as an occurrence that received the new offset.
- An actionable occurrence presents its formatted template amount first. Its
  confirmation amount becomes editable through an explicit secondary action so
  an approximate amount can still be corrected without editing the rule.
- Actionable occurrences are grouped by due date. Each date is stated once,
  while type and status remain visible on every occurrence. Amount correction,
  confirmation and secondary actions form one compact decision area.
- A fund-allocating transfer names that side effect beside the action and uses
  an explicit transfer-and-allocate action.
- Disabling a rule explains that untouched future occurrences are cancelled;
  manual and confirmed decisions are preserved.
- Editing a rule on a narrow screen moves focus context to the existing form;
  archived references already used by that rule stay named, but an active rule
  must select available references before it can be saved.

## Form rules

- Type is explicit: income, expense or transfer.
- Amount is an unsigned exact decimal with the base currency visible. The field
  accepts exact addition and subtraction expressions and resolves them on blur.
- Income and expense require a matching category and one account.
- Transfer requires two different accounts and no category.
- A transfer may opt into immediate distribution across active funds by their
  configured percentages; the option is visible only for transfers and states
  that percentages are resolved when the occurrence is confirmed.
- Start date is visible; end date is optional and inclusive.
- Weekly rules expose weekday checkboxes and an every 1–3 weeks interval.
- Monthly rules expose the anchor day through `start_on` and an every 1–3
  months interval. Yearly rules keep the month/day while the year advances.
- Monthly rules explain the supported 1–28 day range before submission.
- Description is optional and used as the human calendar title.
- Omitting the end date means recurrence continues indefinitely; only the next
  year is materialized at any given time.
- Long checkbox choices retain their native control size and align the control
  with the first text line when the label wraps on a narrow screen.
- A calendar day keeps a compact, stable row height and exposes details through
  its date or signed daily amount, without rendering individual occurrence
  cards in the month grid.

## Deliberately deferred

- Drag-and-drop rescheduling.
- Notification delivery outside the application.
- Forecast balances or insufficiency projections inside calendar cells.
- Final decision whether Calendar and Forecast share a permanent top-level
  “Plan” container.

## Multilingual presentation

The implemented RU/EN presentation follows the shared
[internationalization contract](../internationalization.md). Language changes
update screen copy and accessible labels while preserving financial semantics,
user-entered data, dates, selected context and exact monetary payloads.
