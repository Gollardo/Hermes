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

## Presentation refinement (2026-09-11)

The file, format profile, account and explicit fact date form the primary setup
block. Existing native details disclose format and column settings; the summary
keeps the selected profile and search window visible. Settings start collapsed
before upload, open for a file without a selected profile, and collapse for
review. Manual expansion remains available. XLSX exposes worksheet selection;
CSV exposes encoding and delimiter controls. Hiding controls preserves mapping
values and does not change parser or API behavior.

The screen reuses global panel, secondary action, hint and error treatments,
without importing another page's stylesheet. Local grids own field spacing;
long mapping values receive full rows, short numeric settings are bounded, and
the profile name stays beside its save action. Narrow layouts stack controls.

Review rows lead with their description and exact formatted amount. Completed
rows retain status, operation link and source details without a disabled action
selector. Unrecognized rows remain visible with a textual error. Source data
follows financial context and retains its original values. An empty selection
explicitly states that it causes no account changes. Posting rules, all-row
review, matching, receipts and financial calculations are unchanged.
