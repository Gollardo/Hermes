# Hermes

Hermes is a single-owner personal-finance context that keeps actual financial
facts, planned events and imported bank evidence distinct.

## Statement import

**Fact date**:
The calendar date on which an imported row becomes an actual financial
operation in Hermes.
_Avoid_: File date, import date

**Source date**:
The original calendar date parsed from a statement row before any reviewed
manual correction of its fact date.
_Avoid_: Fact date, import date

**Source description**:
The original merchant or operation text supplied by a statement row. It remains
source evidence and may support matching without becoming the operation
description.
_Avoid_: Comment, operation description

**Operation description**:
Optional user-owned text that describes an actual financial operation in
Hermes. It is distinct from the statement's source description.
_Avoid_: Source description, bank comment

**Import period**:
The inclusive source-date range used to select statement rows for review.
It remains distinct from the posting period after fact-date corrections.
_Avoid_: Posting period, file date

**Posting period**:
The inclusive range from the earliest to the latest reviewed fact date among
the rows selected for posting.
_Avoid_: Import period, file date
