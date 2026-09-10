# Recurring and expected operations

## Owner-confirmed lifecycle

A recurring rule does not affect actual balance. It materializes expected
occurrences. A user may `confirm`, `postpone` or `cancel` an occurrence. Internal
status candidates are `pending`, `confirmed`, `postponed` and `cancelled`.

Only confirmation creates an actual financial operation that affects balance.
Postponing one occurrence changes only that occurrence by default. A rule may
explicitly opt into shifting its untouched later occurrences by the same delta.
Confirmation may replace the selected occurrence's operation snapshot after a
reviewed edit. Type, accounts, category, amount, description and the existing
transfer-allocation choice then apply only to that occurrence; its rule and
siblings remain unchanged. A future occurrence confirmed early posts the fact
on application today, while today's and overdue recurring occurrences retain
their due date as the fact date.

## One-off plans

A future income, expense or transfer is stored as a one-off expected occurrence,
not as a future journal fact. It has `source_kind = one_off`, no recurrence rule
and the same pending/confirmed/cancelled lifecycle used by Calendar. Creation,
editing, cancellation and date changes create no physical or fund movements.
The forecast includes pending one-off plans and excludes confirmed or cancelled
ones.

Applying a one-off plan always posts the fact on application today in the
configured Hermes timezone, even when the plan is early or overdue. Posting and
linking `actual_operation_id` share one transaction; a retry returns the linked
operation. Confirmed and cancelled plans cannot be edited. Balance adjustments
are deliberately excluded because they describe an already-known fact.

## Terms and boundary

- **Recurrence rule** describes a repeating intent.
- **Expected occurrence** is a dated, mutable plan generated from the rule.
- **Actual operation** is a posted operations-module fact linked after
  confirmation.

Scheduling owns rules and occurrences; operations owns posting. Confirmation is
a transactional cross-module use case. The flow appears in
[data-flow.md](../architecture/data-flow.md).

## Confirmed recurrence and materialization policy

In plain language, the first-release recurrence editor intentionally supports a
small predictable subset: every day; selected weekdays every one to three
weeks; the same date every one to three months, limited to dates 1–28; or once
per year except 29 February. It prepares instances only one year ahead when the
calendar/materialization command runs, not through a background service. An
unbounded rule itself continues beyond that stored one-year window.

- Supported frequencies are `daily`, `weekly`, `monthly` and `yearly`.
- Weekly rules select one or more ISO weekdays and repeat every 1–3 weeks.
  Monthly rules repeat every 1–3 months on the `start_on` day. Yearly rules
  repeat on the month and day of `start_on`; its year advances automatically.
- `start_on` anchors the recurrence; `end_on` is optional and inclusive.
- Monthly starts are limited to days 1–28. Yearly rules cannot start on
  29 February. A nonexistent occurrence date is never silently shifted.
- Materialization includes today through the same calendar date one year ahead,
  evaluated in the configured application timezone.
- A rule without `end_on` has no implicit one-year end. Each materialization
  advances the physical occurrence window to one year from its current date.
- The first recurring rule locks the application timezone. There is no implicit
  reinterpretation of persisted calendar dates.
- `(rule_id, scheduled_on)` is the deterministic identity. Repeated and
  concurrent materialization cannot create duplicates.
- `scheduled_on` remains the source identity. Postponing changes only `due_on`
  and keeps persistent status `postponed`.
- A rule-level accumulated day offset controls newly materialized occurrences
  after a series shift. Each occurrence stores its applied offset snapshot.
- An automatically cancelled occurrence preserved by a later series shift has
  an explicit preservation marker. The marker is valid only while the
  occurrence remains automatically cancelled and is mutually exclusive with a
  manual modification; its offset snapshot continues to describe the date
  actually applied to that occurrence.

## Rule editing policy

An occurrence is protected from implicit rule updates after confirmation or any
manual postponement/cancellation. Other generated occurrences are synchronized:

- matching dates receive the current rule snapshot;
- dates no longer produced are automatically cancelled;
- newly produced dates are materialized;
- disabling a rule automatically cancels its untouched future occurrences.

Past pending occurrences are preserved as overdue and require an explicit
confirm, postpone or cancel action.

Re-enabling or another edit may restore an automatically cancelled occurrence,
but never one cancelled manually. If a later series shift preserves an
automatically cancelled occurrence as a dated exception, subsequent
materialization does not restore it. This protection is represented by the
  explicit preservation marker rather than inferred from offset differences.

The uniqueness identity applies only to recurring occurrences. A database
constraint requires a recurrence rule for `recurring` and forbids one for
`one_off`, so materialization never touches a one-off plan.

Migration `0014_one_off_plans` refuses a downgrade while one-off plans exist.
The preceding schema cannot preserve them, so a rollback requires their
intentional removal or a restore to a pre-plan backup rather than silently
discarding plan history.

In practical terms, changing a rule updates only untouched current and future
instances. Anything already confirmed, postponed or manually cancelled keeps
the exact decision the owner made.

## Financial invariants

- Rules and expected occurrences never create account or fund movements.
- Confirmation posts exactly one actual operation and links it atomically.
- Confirmation may replace the selected occurrence's reviewed operation fields.
  The confirmed snapshot records the accepted values and future siblings keep
  the rule snapshot.
- A transfer snapshot may request percentage allocation on the destination
  account. Its physical transfer, fund allocation and confirmation link commit
  or roll back together. The percentages are read from one locked active-fund
  snapshot at confirmation time; missing positive percentages fail explicitly.
- A failed posting leaves the occurrence actionable and unlinked.
- Confirming an already confirmed occurrence is idempotent.
- With series shifting disabled, postponing changes neither the rule nor its
  siblings and depends only on the occurrence version. With it enabled, the
  request also carries the rule version; the rule offset and later non-confirmed,
  non-manually-modified occurrences move by the same exact calendar-day delta
  in one transaction. Earlier, confirmed and manually changed occurrences are
  preserved.
- A series postpone locks the rule, selected occurrence, later pending
  occurrences and automatically cancelled occurrences that need an explicit
  preservation marker. Confirmed, manual and already protected exceptions are
  counted in the response without taking row locks. Candidate rows are selected
  in deterministic `(scheduled_on, id)` order.
- Disabling the option later stops future propagation but does not undo shifts
  already applied.
- Rule synchronization also revisits already materialized future occurrences
  whose shifted due dates lie beyond the current creation horizon. Disabling or
  shortening a rule therefore cannot leave those occurrences actionable.
- A concurrent rule edit either precedes confirmation and invalidates its stale
  optimistic version, or follows it and preserves the confirmed snapshot.

## Calendar read policy

- The monthly grid loads every API page in its bounded 42-day range, so a large
  number of rules cannot silently hide calendar events.
- The action list intentionally shows the first 12 pending/postponed events and
  displays both the visible and complete filtered counts.
- A confirmed occurrence links to its exact actual operation; its stored
  schedule snapshot is not relabelled as the current financial fact.

The complete decision and persistence consequences are recorded in
[ADR 0003](../decisions/0003-recurring-rules-and-occurrences.md).

## Deferred questions

- Richer recurrence expressions beyond the implemented weekly/monthly interval.
- A user-selectable missing-day policy for dates 29–31 and leap day.
- Background materialization without an external job queue.
- Migration semantics if instance timezone changes after schedules exist.

## Explicit import confirmation

Statement import can close one pending/postponed occurrence on the user-selected
fact date, including a historical date. Bank dates are not applied. The original
schedule dates and recurrence identity remain unchanged; accepted operation
fields update only that occurrence. An existing compatible fact can be linked
without creating physical/virtual movements again. An operation already linked
to another occurrence is rejected. Stale versions and cancelled/confirmed
occurrences cannot be claimed by another import decision. Ordinary Calendar
confirmation keeps its existing date policy. See [ADR 0005](../decisions/0005-statement-import.md).
