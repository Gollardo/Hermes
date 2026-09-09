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

## Release 0.1.0-alpha.1 behavior

An **uninitialized instance** has no owner credential.
`GET /api/v1/setup/status` reports that state without exposing settings.
`POST /api/v1/setup` atomically creates the owner credential, application
settings, persistent login-throttle state and the first session. Fresh setup may
create owner-selected category templates through the application coordinator.
First-run restore validates a versioned backup and creates the destination
credential, session, restored settings and financial data in one transaction. A
repeated setup returns a conflict and cannot replace the credential or
preferences.

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
- Failed login state persists across process restarts. By default, five failures
  in a rolling 15-minute window block all login attempts for 15 minutes. A
  successful login clears the counters.
- Password changes never leave older browser sessions authenticated.

## Explicit release assumptions

- New master passwords contain 12–1024 Unicode characters. No additional
  composition rule is imposed.
- Idle expiry is 30 minutes. “Remember me” remains deferred.
- Login throttling is instance-wide because there is one owner and client IP is
  not a reliable identity behind an unspecified reverse proxy.
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

## Multilingual setup and validation

Language selection is available before authentication and grants no additional
access. Optional fresh category templates use an independently selected RU/EN
language while preserving atomic setup. The API validation boundary returns safe
field/type metadata without echoing input or exception context. Session, password,
CSRF and throttling rules are unchanged. See the
[internationalization contract](../ui-ux/internationalization.md).
