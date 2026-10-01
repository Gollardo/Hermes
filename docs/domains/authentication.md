# Authentication

## Confirmed product boundary

- Hermes has exactly one local owner. Registration, multiple users, roles,
  permissions, organizations, invitations and tenants are out of scope.
- First run creates the owner credential once. A committed credential makes
  setup permanently unavailable through the normal application flow.
- Authentication uses an Argon2id master-password hash and revocable
  server-side sessions. JWT and external identity providers are not used.
- Every API route is authenticated by default except health, setup status,
  fresh setup, first-run setup restore and login.

## Current behavior

An **uninitialized instance** has no owner credential.
`GET /api/v1/setup/status` reports that state without exposing settings.
`POST /api/v1/setup` atomically creates the owner credential, application
settings, persistent login-throttle state and the first session. Fresh setup may
create owner-selected category templates through the application coordinator.
First-run restore validates a versioned backup and creates the destination
credential, session, restored settings and financial data in one transaction. A
repeated setup returns a conflict and cannot replace the credential or
preferences.
Both setup coordinators reject initialized state before expensive work. A
non-blocking PostgreSQL transaction advisory lock admits one setup/login password
worker across processes; setup checks ownership again after admission to close
the concurrent-initialization race. Busy setup returns `429 auth_work_busy`
with `Retry-After: 1`, without creating partial state.

An uninitialized deployment is bound to loopback by default and must be claimed
locally before it is exposed to another network. The public setup endpoint has no
user credential to authenticate until that one-time operation succeeds.

The browser receives a random session identifier in an HttpOnly, SameSite=Lax
cookie. PostgreSQL stores only its SHA-256 digest. Sessions have a seven-day
absolute lifetime and a 30-minute inactivity limit by default. Both are checked
on every protected request. A narrow CSRF-protected heartbeat advances the
activity timestamp; ordinary business reads remain read-only.
The browser independently hides the protected shell at the same deadline and
sends a throttled keepalive only while it observes owner interaction. Login
rotates both session and CSRF tokens. Expired session rows are pruned during a
successful login; no background cleanup system is introduced.

Setup, login and current-session responses include the effective idle duration,
so runtime tuning cannot leave the browser and backend deadlines inconsistent.

State-changing authenticated requests use a double-submit CSRF token. Its
non-HttpOnly cookie is readable by the same-origin Angular client and must match
the digest attached to the server-side session. The session identifier remains
HttpOnly. Cookies are `Secure` by default in production and non-Secure in the
development Compose environment.

Logout deletes the current session. “Logout all” deletes every session,
including the caller. Changing the master password requires the current
password and revokes every other session while retaining the current one.

## Security invariants

- There can be at most one owner credential; the database enforces singleton
  identity `1`.
- Plain master passwords, session identifiers and CSRF tokens are never stored.
- Setup credential creation, initial preferences, optional category templates
  or restored backup data, and first session commit in one database transaction.
- Successful setup, login and mutation responses are not sent until their
  database transaction commits.
- A missing, unknown or expired session receives `401` before a protected use
  case runs.
- Idle rows are rejected immediately and pruned with other expired rows during
  the next successful login; parallel business reads never race to rewrite the
  same session row.
- A state-changing request with an absent or wrong CSRF token receives `403`.
- Failed anonymous login state persists per resolved network source across
  process restarts. By default, five failures in a 15-minute window block that
  source for 15 minutes. Successful login clears only its source counters.
- Anonymous failures never update or clear the separate singleton sensitive-action
  counter. Password change, protected export and initialized restore share that
  counter: five failures block sensitive password verification for 15 minutes.
  Invalid/blocked responses commit accounting without changing credentials or data.
- One anonymous password worker runs at a time across processes. A persisted
  admission deadline defaults to 250 ms between attempts across all sources.
  Distributed callers cannot bypass this budget; busy requests receive a short
  `429 auth_work_busy` response. Already-blocked sources do not move the deadline.
- Source state is capped at 4096 rows and expired rows are reclaimed during login.
  At capacity, new sources still verify under the global work budget without
  storing another row; existing source blocks remain effective. This prevents
  table saturation from blanket-blocking a correct owner password. Per-source
  accounting is unavailable for overflow sources until capacity returns.
- Password changes never leave older browser sessions authenticated.

## Explicit release assumptions

- New master passwords contain 12–1024 Unicode characters. No additional
  composition rule is imposed.
- Idle expiry is 30 minutes. “Remember me” remains deferred.
- Source identity defaults to the actual connection peer. Uvicorn must run with
  `--no-proxy-headers`, as supplied container commands do. `X-Forwarded-For` is
  ignored unless that peer belongs to `HERMES_TRUSTED_PROXY_NETWORKS`; trusted
  chains are walked from the connection side to the first untrusted address.
  Malformed, duplicate or oversized chains fall back to the connection peer.
  Sources behind the same NAT or an unconfigured proxy share a failure bucket.
  A network source is an abuse-control hint, never an authenticated identity.
- `HERMES_LOGIN_ADMISSION_INTERVAL_MS` defaults to 250; setting it to zero
  disables pacing while retaining concurrency admission. Zero is used only for
  deterministic integration scenarios here, not the deployment recommendation.
- Password recovery is intentionally absent. Losing the master password
  requires an out-of-band, future recovery design; normal setup cannot be
  reopened.

These values are implementation defaults selected to complete the release, not
permanent owner-approved product policy. Deployment operators can tune session
and throttling durations with the documented `HERMES_*` environment variables.

## Remaining work

- Design a safe local recovery procedure.
- Decide whether long-lived remembered sessions are needed.
- Add scheduled cleanup only if expired-session accumulation becomes material.
- Document tested HTTPS reverse proxies and forwarded-header policy.

## Unreleased request admission

Before JSON parsing and database/authentication dependencies, every API request
has a streamed byte budget: 64 KiB for authentication and fresh setup, 16 MiB
for financial/import routes, and the existing 72 MiB for backup routes and
setup restore. These are transport limits, not changes to financial precision
or domain arithmetic. Both declared length and actual received chunks are
checked; missing or underreported `Content-Length` cannot bypass the budget.
Oversize returns `413 request_too_large` or the existing `backup_too_large`.
RU/EN notices preserve form values and permit retry. Backup payload limits and
Argon2 parameters are unchanged. Migration `0017_auth_admission` adds source
throttle storage and the admission timestamp, and clears legacy anonymous blocks
from the now exclusively sensitive-action counter. Authentication state remains
excluded from portable backups.

## Multilingual setup and validation

Language selection is available before authentication and grants no additional
access. Optional fresh category templates use an independently selected RU/EN
language while preserving atomic setup. The API validation boundary returns safe
field/type metadata without echoing input or exception context. Session, password,
CSRF and throttling rules are unchanged. See the
[internationalization contract](../ui-ux/internationalization.md).
