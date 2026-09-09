# Multilingual release acceptance — 2026-09-09

## Result

The four findings from the initial `6a896b2` audit were fixed and manually
retested before [release 1.1.0](https://github.com/Gollardo/Hermes/releases/tag/v1.1.0).
The owner subsequently authorized publication. This record preserves acceptance
evidence and coverage limits; reproduction instructions for closed defects and
temporary container handoff details have been removed.

## Data and environment

An isolated loopback-only production Compose instance with PostgreSQL 17 used
an owner-supplied app-1.0.0/schema-1 backup. Its SHA-256 was
`3a796150d96fe656a628b33fad3f3d022e9790ef2327fe7ce9e606e5ed0a97d4`.
Neither the source file nor production was changed. Browser checks used Chrome
and the Codex in-app browser on macOS; targeted fixes were retested in Chrome.
Initial temporary credentials were provisioned through the setup API, so this
run does not certify first-run restore through the UI.

After restoring the source again, browser JSON export matched the complete
source `data` object, including list order and all record fields. Protected
`.hermes` export was decrypted through the public opener and matched too.
The dataset contained 2 accounts, 86 categories, 169 operations, 176 physical
movements, 6 funds, 16 fund events, 76 virtual movements, no reserve movements,
18 rules and 1145 expected occurrences. Authentication remains destination-local
and is not portable backup data.

## Verified scenarios

| Scenario | Result |
| --- | --- |
| Sign-in and errors | Valid login, localized wrong-password rejection and language changes passed |
| Restore | Valid preview, Russian restore and corrected English button submission passed; invalid backup rejected |
| Financial facts | Income create/edit/delete, exact four-place input, overdraft rejection and neutral account transfer passed |
| Planning | One-off creation was balance-neutral, affected forecast by the exact amount and could be cancelled |
| Funds and reports | Allocation preserved physical money; history loaded; report totals matched source and visible expense shares totaled 100.00% |
| Stored content | Names, category hierarchy and descriptions remained unchanged in English |
| Data round trip | Final JSON and protected export retained source data |

## Closed findings

- English restore: prompt, disabled condition and handler now share the selected
  phrase while retaining the published API command. Actual button submission and
  changing language after entering a phrase were retested.
- Operation rejection: readable alert appears in the active composer in RU/EN,
  including at 390 px; exact input `999999999.1234` survives rejection.
- Copy: rule summary/editor use `+1 day` / `+1 день`; Russian backup count labels
  avoid incorrect noun inflections. Automated cases also cover +2/+5/-1.
- Forecast: two non-overlapping endpoint labels fit a 390-pixel viewport in both
  languages; desktop resize restores more labels without changing source points.

Rendered regressions cover the above guards, retry data, plurals and resizing.
The full release checks are summarized once in [project status](../project-status.md#release-verification).

## Coverage limits

This bounded pass did not exercise password changes, lost-session races,
first-run restore UI, every recurring/fund/CRUD action, all forecast horizons or
exhaustive Safari/VoiceOver behavior. Alert semantics were asserted; actual
screen-reader announcement was not certified. A rejected submit may leave focus
on the document after disabling the submit button. Inputs remain available for
recovery; enhanced focus management is still unverified.
