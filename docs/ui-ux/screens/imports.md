# Statement import

## Visual refresh — 2026-09-26

Setup field groups and the review summary adopt the shared surface hierarchy.
File mapping, duplicate/plan review, merge consent, exact inputs, retry identity
and posting boundaries are unchanged.
See [atlas refresh](../atlas-refresh.md). This records implementation under the
owner-authorized redesign, not separate final visual acceptance.

## Status

Implemented as a separate `/imports` review flow entered from the operation
journal. Uses existing page, field, state, exact-money and responsive patterns.
This is not a replacement design system.

The source-date mapping slice is implemented: profiles record the source-date
column and bounded text format, native XLSX dates need no text format, and each
recognized row starts with its own editable fact date. Invalid dates remain
visible and correctable. Import-period filtering and the searchable
reconciliation controls described below remain in progress.

## User flow

1. Upload CSV or XLSX; choose worksheet, header, column mapping and CSV settings.
2. Reuse or save a format profile. Choose the account and map the statement
   column and explicit text format that supply row fact dates. Native XLSX date
   cells do not require a text format.
3. Review every data row, including pending, completed, unknown-status and
   invalid rows. Bank dates/statuses appear only in expandable source details.
4. Choose skip, new fact, planned payment or existing fact. Category suggestions
   remain editable in the established searchable category combobox, with the
   parent-child path visible. Planned payments use a searchable combobox with
   suggestions first and the remaining eligible window available. Suggested
   facts/plans explain matching amount, description and date.
5. Review the actual date, type, category, accounts, optional fund, selected
   plan/existing fact and account effects. A transfer requires both accounts.
6. Confirm the selected batch. Success appears only after database commit.
   Errors preserve the review for correction and retry. Completed rows are
   excluded from further submission and link to the journal. The summary shows
   ascending fact-date posting order, with source order retained within a date.

## Contracts

The mapped statement date supplies each row's editable fact-date default; no
date comes from the browser. The selected rows expose their derived inclusive
import period. An optional inclusive start/end filter defaults to that complete
period, shows the number of excluded rows and can be reset. Source amounts remain exact;
rendering uses two fractional digits and never rewrites the payload. All strings
are RU/EN except user/source values. Mapping changes invalidate the preview.
The user must rerun review after a stale fact/plan conflict. Empty selections
cannot post. Desktop forms reorganize into one column on narrow screens;
source details wrap instead of overflowing. Financial effects are text, never
color-only. File/draft state is browser memory only and is lost on reload.

Missing, invalid and future dates keep their rows visible and blocked until
corrected or skipped; there is no implicit date fallback. A source date-time
uses its written calendar date without timezone conversion.

The range filter uses source dates. The review and confirmation summaries label
the source-date import period separately from the fact-date posting period.
If a corrected fact date lies outside the import period, the row stays selected
and a warning explains the expanded posting period. Filtering a row out keeps
its browser-draft edits; resetting the filter restores the edited row. Reloading
the page still clears the draft.

## Presentation refinement (2026-09-11)

The file, format profile, account and date-column mapping form the primary setup
block. Existing native details disclose format and column settings; the summary
keeps the selected profile, derived import period and search window visible.
Settings start collapsed
before upload, open for a file without a selected profile, and collapse for
review. Manual expansion remains available. XLSX exposes worksheet selection;
CSV exposes encoding and delimiter controls. Hiding controls preserves mapping
values and does not change parser or API behavior.

A legacy profile without a date mapping remains readable, but review requires
the owner to select the date column and text format and then offers to resave
the profile. The screen does not silently restore the old shared-date control.

The screen reuses global panel, secondary action, hint and error treatments,
without importing another page's stylesheet. Local grids own field spacing;
long mapping values receive full rows, short numeric settings are bounded, and
the profile name stays beside its save action. Narrow layouts stack controls.

Review rows lead with source context and the exact formatted amount. A new fact
starts with an empty optional operation description and offers an explicit
copy-from-source action. Choosing a plan uses its description; linking an
existing fact preserves the existing description. These description controls
and outcomes are implemented in the 2026-10-21 refinement slice. Completed
rows retain status, operation link and source details without a disabled action
selector. Unrecognized rows remain visible with a textual error. Source data
follows financial context and retains its original values. An empty selection
explicitly states that it causes no account changes. Posting rules, all-row
review, matching, receipts and financial calculations are unchanged.

## Explicit plan-row grouping

Selecting one plan on several rows exposes an unchecked merge control in the
review summary. The user must explicitly accept the group before posting.
The summary shows source row numbers, the exact formatted total, selected date
and the selected plan description. It explains that the
group posts at its first member's position. Each row still exposes its account,
category, fund and original source details. Incompatible groups explain the
required matching date, type, account, category and fund; existing facts and
transfers cannot be merged. Group errors preserve every row and selection.
Successful members link to the same journal operation and cannot resubmit.
A refreshed preview resets merge consent. No automatic grouping or partial
settlement is introduced. Checkbox labels wrap with a fixed native control size
at narrow widths, reusing the established form pattern.

Candidate plans are evaluated separately around each row's editable fact date,
using the existing default window of three days before and after that row.
Source descriptions remain visible in each member's source details.
The user may widen the window for one row without changing its fact date.

All rows default to skip. Suggestions never choose a posting action. Category
search matches within both the parent and child names, so a query need not start
at the beginning of the displayed path.

An active category root is a selectable row. Active children appear beneath it
with indentation and a supporting `Parent → Child` path. Archived categories
are absent from new-fact choices but remain visible for existing facts.

The existing-fact control is also a searchable combobox. Likely duplicates
remain first; search covers date, operation description, category and exact
amount. More than 200 selected rows block confirmation and direct the owner to
narrow the period. The screen does not split a confirmation automatically.
Bulk action, category and plan assignment are outside this refinement.

After posting, operation details may expose the receipt's original source date
and source description. The complete source row and file remain available only
during the active browser review and are not persisted.
No separate import-history screen is introduced.
