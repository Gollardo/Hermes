# Replacement savings

## Scope and primary question

The implemented screen answers: how much should I set aside this month for each
replacement purchase, how much is already saved, and where is it held? It uses
existing page, panel, modal form, searchable account and exact-decimal patterns.
The visual direction remains preliminary; no new design system is introduced.

Each purchase shows saved money, its inflation-adjusted estimated target, the
end month and the current monthly recommendation/remaining contribution. Text
states distinguish saving, funded, expired and archived purchases. Details
contain original inputs, account positions, a month-based schedule and explicit
contribution/release history; linked physical transfers open their journal fact.
Future schedule rows are estimates and explain their assumptions.

Creation asks for cost, purchase month, term and expected annual inflation. A
server preview presents the derived target and initial pace before creation.
Changing input invalidates that preview. There is no editable final-price field.
The preview creates no reservation or purchase expense.

Contribution explains the reduction in free money, selects the holding account
and optionally another source account. Without a source it only reserves money
already held. Release explains that money becomes free without physical movement
or an expense. Archival is offered with an explanation at zero balance only.

Failed requests retain input; a refresh action retrieves the current version.
Identical transport retries retain the request UUID. Loading and error states
must not be presented as zero savings. RU/EN catalogs update labels and month
names while preserving entered values. Money retains the shared comma/two-place
format in both languages; no binary float calculation is used in the frontend.
Narrow layouts stack comparable values and month rows instead of clipping them.

The Funds screen displays replacement reservations separately in its total and
per-account coverage. These purchases are excluded from ordinary fund selectors
and allocation controls. A link opens the dedicated screen.
