# Deployment runbook

This is the deployment path for the current pre-1.0 release line, not a complete
security-hardening guarantee. Its owner-confirmed support boundary is a
protected environment: loopback or a trusted network, with VPN or an HTTPS
reverse proxy for remote access. Direct public-internet exposure is unsupported.

## Prepare

1. Install Docker and Compose on the target host.
2. Copy `.env.example` to `.env` and replace `POSTGRES_PASSWORD` with a long,
   unique value. Restrict file permissions on the host.
3. Keep `APP_BIND_ADDRESS=127.0.0.1` through the one-time setup. A fresh
   instance has no owner credential yet, so publishing it on a LAN would let
   another network client claim the first setup.
4. Arrange a VPN or HTTPS reverse proxy for any remote access.
5. Keep `HERMES_COOKIE_SECURE=true` whenever the browser uses HTTPS. For a
   loopback-only plain-HTTP check, explicitly set it to `false`; never combine
   that override with a LAN-facing bind address.

`HERMES_SESSION_IDLE_MINUTES` defaults to `30` and is passed through both
Compose configurations. Authentication responses publish the effective value
to the Angular shell, keeping its visible deadline aligned with the backend.

Validate and start:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Verify both API and Angular through the same port:

```bash
curl --fail http://localhost:8000/api/v1/health
curl --fail http://localhost:8000/
```

On a clean database, opening the Angular URL presents the one-time setup screen
with a choice between atomic JSON restore and a fresh start. After setup,
subsequent browsers see the master-password login screen. The app
container applies all migrations through the current Alembic head
automatically before serving traffic.

Complete setup from the host over loopback before changing `APP_BIND_ADDRESS`.
Only after setup may an operator deliberately use `0.0.0.0` for LAN access, and
then only behind the VPN or HTTPS controls described above. Restoring an empty
database reopens setup and requires repeating this trusted-loopback procedure.

Inspect logs with `make logs`. The app waits for healthy PostgreSQL, applies
Alembic upgrades and then starts as a non-root user. PostgreSQL is not published
to the host.

## Unreleased security admission and proxy setup

Migration `0017_auth_admission` adds per-source login counters and an aggregate
admission timestamp. It resets legacy anonymous failures from the separate
sensitive-action counter; credentials, sessions and financial records are unchanged.
Take a verified backup before upgrading; test the migration against a disposable
copy. No backup-schema change or authentication-state export is introduced.

Container commands disable Uvicorn's automatic proxy-header handling. Native
commands must also include `--no-proxy-headers`. For a reverse proxy, set
`HERMES_TRUSTED_PROXY_NETWORKS` to a JSON array of its actual narrow networks,
for example `["172.20.0.2/32"]` after confirming that address in your deployment.
The default `[]` ignores forwarded client addresses. The proxy must replace or
append the real connection address to `X-Forwarded-For`, and direct backend
access must be restricted. Never trust every address or an arbitrary incoming
header. Requests behind an unconfigured proxy or the same NAT share a source
failure bucket; correct source mapping requires live acceptance, not just config.

`HERMES_LOGIN_ADMISSION_INTERVAL_MS=250` spaces anonymous password work across
all sources. One setup/login cryptographic worker is admitted at a time across
application processes sharing the database. Temporary saturation returns
`429 auth_work_busy` with a short retry hint. Source lockout is separate from
sensitive password verification; a hostile source cannot set the latter's block.
Do not disable pacing in production merely to make a load test pass. Capacity
overflow retains known source blocks and uses aggregate admission for new sources.

The API streams body limits before parsing: auth/fresh setup 64 KiB,
financial/import routes 16 MiB, backup/setup restore 72 MiB. Apply matching or
stricter upstream limits deliberately, allowing supported imports and backups.
After upgrading, verify the real HTTPS URL/cookies, source resolution, rejection
of missing/false-length oversized requests, independent owner login, and isolated
backup/restore. These local code changes do not certify TLS, proxy policy, host
storage protection or resistance to volumetric network exhaustion.

## Stop and restart

```bash
docker compose stop
docker compose start
```

`docker compose down` removes containers/network but retains the named database
volume. Do not add `--volumes` unless intentionally destroying persistent data
after a verified backup.

## Upgrade outline

Before an upgrade: read release notes, create and test a backup, pull or checkout
the intended version, then run `docker compose up -d --build`. Automatic Alembic
upgrade runs before the new process. Downgrading application code after a schema
upgrade is not guaranteed; restore the verified pre-upgrade backup if rollback
is required.

See [backup and restore](backup-and-restore.md) and the
[security policy](../../SECURITY.md).
