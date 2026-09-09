# Multilingual acceptance on a restored production backup

## Verdict

The initial acceptance pass against `6a896b2` found four defects described below.
All four were subsequently fixed in the working tree and manually retested on
2026-09-09 using the rebuilt production image. **The recorded defects are closed;
owner release acceptance remains outstanding.** No production service or source
backup was changed. The initial findings and coverage are preserved as history.

## Environment and evidence boundary

- Built the repository's production Dockerfile successfully, without fallback
  images or dependency substitutions. Image: `hermes:real-data-acceptance`,
  digest `sha256:f473ccd1534a40b8fde6e6addb68abbf3d628ebf3cd9110d6808c7e3ba19d4b0`.
- Separate Compose project `hermes-acceptance`, PostgreSQL 17 and a dedicated
  volume. App binding: `127.0.0.1:18089`; PostgreSQL has no host port.
  Local HTTP uses non-secure cookies only on this loopback test instance.
- Source: owner-provided plaintext schema-1 backup, app version 1.0.0.
  SHA-256: `3a796150d96fe656a628b33fad3f3d022e9790ef2327fe7ce9e606e5ed0a97d4`.
  The source file was never edited. No production service was contacted.
- Initial temporary owner credentials were provisioned through the setup API.
  Sign-in, file preview, initialized-instance restore and test actions used the
  browser. This does not certify first-run restore through its UI.
- Browsers: Codex in-app browser and Chrome on macOS. Desktop and 390-pixel
  mobile layouts were inspected. Native browser dialogs retain the OS language.
- The browser driver had native-dialog and file-upload limitations. Chrome's
  native confirmation and file picker were used to complete those actions.
  These tool limitations are not classified as Hermes defects.
- Tests used only the local restored copy. After testing, the original backup
  was restored again through the Russian UI, removing every test change.

## Initial scenario results (before fixes)

| Scenario | Result | Evidence |
| --- | --- | --- |
| Production container startup and migrations | Pass | Standard image built; app served UI/API; PostgreSQL healthy |
| Wrong password and language switch on login | Pass | Localized rejection; existing error changed from RU to EN |
| Valid local sign-in | Pass | Both browsers opened the application |
| Backup file preview | Pass | Integrity confirmed; counts matched the source |
| Initialized restore in English | **Fail, P1** | Correct English phrase and password leave the button disabled; reproduced in both browsers |
| Initialized restore in Russian | Pass | Completed twice, retaining destination credentials/session |
| Invalid backup | Pass | Unsupported/malformed test document rejected with readable English error |
| Restored overview and accounts | Pass | Decimal reconstruction from source movements matched all displayed baseline balances |
| Journal | Pass | 169 restored operations, 7 pages and correct full-selection total |
| Income creation | Pass | `1000,50 + 0.25` produced an exact 1000.75 income |
| Income edit and removal | Pass | Four-place input displayed using HALF_UP; removal restored the original journal total |
| Overdraft prevention | Partial | Server rejected the expense; error was hidden behind the modal (P2) |
| Account creation and precision | Pass | Input 12.3456 stored as NUMERIC 12.3456 and displayed as 12,35 |
| Account transfer | Pass | Test transfer 5.25 decreased one account and increased the other equally |
| One-off plan | Pass | Future date selected plan mode; 123.45 plan left actual balances unchanged |
| Plan in calendar and forecast | Pass | Appeared on the requested date; forecast minimum/end decreased by exactly 123.45 |
| Plan cancellation | Pass | Native confirmation completed in Chrome; plan disappeared from active journal plans |
| Recurring calendar | Pass for reading | 18 rules, current attention items, month grid and date drilldown loaded |
| Fund allocation | Pass | Preview and posting of 10.00 to existing dynamic funds changed free/reserved money, not physical total |
| Restored fund history | Pass | Existing allocations and expenses loaded after the history request completed |
| Expense/income reports | Pass | September totals and operation counts independently matched the source; 16 expense shares summed to exactly 100.00% |
| Category tree | Pass for reading | All 86 categories retained their names and hierarchy in EN |
| RU/EN presentation | Pass with copy defects | Application labels/dates translated; stored descriptions and names retained |
| Mobile layout | Partial | No document-wide horizontal overflow at 390 px; forecast date labels crowded and clipped |
| JSON export after final restore | Pass | Browser download completed; entire `data` object equals the source, including list order and all record fields |
| Protected backup export | Pass | Browser downloaded `.hermes`; public backup opener decrypted it and confirmed identical source data |

The final equality check includes settings, 2 accounts, 86 categories,
169 operations, 176 physical movements, 6 funds, 16 fund events, 76 virtual
movements, 0 reserve movements, 18 rules and 1145 expected occurrences.
Passwords/authentication are destination-local and outside portable backup data.
Browser console inspection returned no JavaScript errors; container logs contained
no server tracebacks or HTTP 500 responses during the observed run.

## Initial findings and required regression tests (resolved below)

### P1 — English restore cannot be submitted

1. Select English in Settings and choose a valid backup.
2. Enter the displayed `REPLACE ALL DATA` phrase and the current master password.
3. Observe that **Restore and replace data** stays disabled.

The button compares the form value against the fixed Russian
`restoreConfirmation` property in `settings.html`, while `restoreBackup()` checks
`t('settings.restorePhrase')` and sends the published Russian protocol constant.
The visible prompt, disabled condition and handler therefore disagree.
Switching to Russian and entering its displayed phrase works.

Fix the UI condition to use the localized phrase without changing the backend
protocol. Add a rendered-component test that fills the fields and clicks the
actual button in both languages. Current handler-level tests bypass this guard.
Also test a language change after entering the phrase.

### P2 — Submission error is obscured by the operation modal

1. Open an expense composer and select an existing category/account.
2. Submit an amount exceeding the available balance.
3. The API rejects it and a localized alert exists, but it is rendered in the
   page behind the modal rather than inside the composer.

Chrome screenshot inspection confirmed that the active form shows no readable
failure explanation. `operations.html` renders the global alert before the
modal backdrop. Keep submission errors inside the active dialog and verify
visual visibility, focus behavior and announcement in a rendered browser test.

### P3 — English singular day wording

Existing shifted rules display `current shift +1 days`. The corresponding
catalog interpolation appends a fixed plural noun. Use the existing plural
helper for both the rule summary and accumulated-shift message; test 1 and 2.
Russian backup summaries also retain forms such as `2 счетов`; count-label
wording or proper plural rules would improve both catalogs.

### P3 — Crowded forecast date scale at mobile width

At 390 px, monthly forecast tick labels visually touch and the last date is
clipped. The document width itself remains 390 px. Choose fewer ticks based on
available chart width and keep edge labels inside the chart; verify RU/EN at
390 px and desktop widths. This does not affect the calculated forecast.

## Remaining coverage and next action

This was a bounded manual acceptance pass, not an exhaustive replacement for
unit/integration suites. It did not exercise password changes, lost-session
races, first-run restore UI, posting recurring occurrences, every fund action,
every CRUD/archive combination, all forecast horizons, Safari or VoiceOver.
The initial audit ran production build and documentation checks only. The
subsequent fix pass ran all repository check targets, as recorded below.

Complete owner acceptance and the standard release checklist before publication.
The untested broader scenarios above remain outside this bounded defect retest.

## Fixes and repeat acceptance — 2026-09-09

The production image used for the repeat run is
`sha256:3513a0791ed2f9c7356a374a18212787ad6b7a21594faa63d2a4001b44c1cc9e`.
It replaces the initial audit image in the same isolated Compose project.
No migration, backend contract, dependency or financial calculation changed.

| Finding | Repeat result | Evidence |
| --- | --- | --- |
| P1 restore button | Pass | Native file picker loaded the original JSON. English phrase and password enabled the actual button. Switching to RU disabled it without rewriting input; the Russian phrase enabled it. Switching back disabled it until the English phrase was entered. Clicking the English button completed restoration and retained English UI. |
| P2 hidden submission error | Pass | Real overdraw attempts in EN and RU returned a readable alert inside the dialog. Desktop and 390-pixel screenshot inspection confirmed visibility in the action footer. The rejected Russian comma input retained `999999999.1234` when refocused; no operation was created. |
| P3 day/count wording | Pass | Existing Линзы rule summary and editor showed `+1 day` in EN and `+1 день` in RU. Russian backup preview used `Счета: 2` and consistent count labels. |
| P3 mobile date scale | Pass | At 390 pixels, both locales displayed two non-overlapping endpoint labels wholly inside the chart, with document width 390. Desktop resize restored seven non-overlapping labels; screenshots and DOM rectangles were inspected. |
| Data preservation | Pass | Browser-downloaded JSON after the repeat run matched the original complete `data` object exactly, including list order and all fields. Original SHA-256 was unchanged. |

Added rendered regression coverage checks both restore languages, locale changes,
password/phrase/busy guards and protocol stability; in-dialog server rejection,
explicit retry and exact amount preservation; signed shifts +1/+2/+5/-1 in both
languages; and responsive endpoint ticks, unchanged forecast points and observer
cleanup. No actual screen-reader announcement is claimed: the alert semantics
are asserted, while VoiceOver remains outside tested coverage. A rejected submit
can leave focus on the document after the temporarily disabled submit button;
the visible alert and retained fields allow recovery, but this does not certify
an enhanced focus-management policy.

Checks after the fixes:

- `make test`: 109 backend tests passed with 69 PostgreSQL-gated skips in the
  default run; the separate PostgreSQL suite passed all 70 integration tests;
  all 171 frontend tests passed in 23 files.
- `make lint typecheck`: Ruff, formatting, ESLint, catalog/source completeness
  (866 keys), documentation validation, mypy and TypeScript passed.
- Production frontend build and standard Dockerfile build passed. Existing
  warning budgets remain: initial bundle 516.44 kB against 500 kB, plus component
  CSS warnings. No budget was relaxed and no dependency was added.
- Container migration head is `0014_one_off_plans`; `alembic check` found no
  new upgrade operations. `git diff --check` passed.
- Chrome console reported no JavaScript errors during the repeat scenarios.

Recommended next step: owner acceptance of this local instance, followed by the
normal release checklist. Operational hardening, additional languages and
unrelated interaction changes remain deferred.

## Local handoff

The test containers remain running for owner inspection at the loopback address.
Compose configuration and the temporary login password are under
`/tmp/hermes-acceptance/` (outside the repository). The final instance contains
exactly the restored source data, not the test records. The control exports
remain in Downloads, including the follow-up JSON ending in `(2).json`. To stop the isolated project without deleting its volume:

```bash
docker compose --project-directory /tmp/hermes-acceptance stop
```
