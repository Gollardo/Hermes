# Security policy

## Reporting a vulnerability

Please use the repository's private GitHub Security Advisory flow when it is
available. Until a public repository location is configured, report only a
minimal, non-exploitable description in the project issue tracker and ask the
maintainer for a private channel. **No security contact email has been assigned
yet.** Do not publish credentials, personal financial data or working exploits.

## Deployment expectations

The project owner confirmed that the current release is intended for a trusted,
protected network rather than direct public-internet exposure. Reachable peers
and supplied files are treated as untrusted even inside that boundary. It
does not remove the need for a strong owner password, secure HttpOnly session
cookies, protected Docker volumes and tested backups.

- Do not expose PostgreSQL to the internet; the production Compose file does not
  publish its port.
- Replace example passwords and keep `.env` out of version control.
- Complete first-run setup while the default `127.0.0.1` bind is still active;
  never expose an uninitialized instance to a LAN or remote network.
- Prefer protected `.hermes` exports and keep their password separately. Treat
  plaintext JSON exports as fully readable financial data.
- For remote access, require a VPN or a maintained reverse proxy with HTTPS and
  keep `HERMES_COOKIE_SECURE=true`.
- End server-side sessions after suspected compromise and keep the host, images
  and dependencies patched.
- Authenticated screens close after 30 minutes without keyboard, pointer, touch
  or scroll activity. Active tabs send a throttled keepalive; the server still
  enforces the idle limit independently on every protected request.

The authentication design is documented in
[the authentication domain](docs/domains/authentication.md). The current stable
application has not undergone an external security audit. Password
 recovery, content-security policy and tested reverse-proxy configurations remain
future hardening work.
