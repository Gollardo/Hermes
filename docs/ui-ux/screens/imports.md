# Statement import

## Status

Implemented as a separate `/imports` review flow entered from the operation
journal. Uses existing page, field, state, exact-money and responsive patterns.
This is not a replacement design system.

## User flow

1. Upload CSV or XLSX; choose worksheet, header, column mapping and CSV settings.
2. Reuse or save a format profile. Choose the account and an explicit fact date.
3. Review every data row, including pending, completed, unknown-status and
   invalid rows. Bank dates/statuses appear only in expandable source details.
4. Choose skip, new fact, planned payment or existing fact. Category suggestions
   remain editable. Suggested facts/plans explain matching amount, description
   and date; the date window exposes additional manual choices.
5. Review the actual date, type, category, accounts, optional fund, selected
   plan/existing fact and account effects. A transfer requires both accounts.
6. Confirm the selected batch. Success appears only after database commit.
   Errors preserve the review for correction and retry. Completed rows are
   excluded from further submission and link to the journal.

## Contracts

No fact date is inferred from the bank or browser. Source amounts remain exact;
rendering uses two fractional digits and never rewrites the payload. All strings
are RU/EN except user/source values. Mapping changes invalidate the preview.
The user must rerun review after a stale fact/plan conflict. Empty selections
cannot post. Desktop forms reorganize into one column on narrow screens;
source details wrap instead of overflowing. Financial effects are text, never
color-only. File/draft state is browser memory only and is lost on reload.
