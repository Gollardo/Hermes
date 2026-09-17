# Backup and restore

## Application backup choices

Open the backup and restore section in Settings. The recommended action creates
a protected `.hermes` file after the current master password is verified. The
file is JSON, but financial data exists only in authenticated ciphertext. The
same password is required to open that particular file; Hermes cannot recover a
forgotten backup password.

The separate plaintext `.json` action remains available for compatibility and
manual inspection. It is not encrypted. Anyone who receives it can read the
financial data, so store and transmit it only through protected channels.
Both export responses disable HTTP caching; the downloaded plaintext file still
requires protected storage.

On an empty destination, choose either file on the first setup step. For a
`.hermes` file, provide its backup password separately from the new destination
master password. Backup validation, credential/session creation
and data restore share one transaction; failure leaves the instance
uninitialized and lets the owner choose another file or start fresh.

On an initialized destination, sign in, choose either file in Settings and
review the count/currency/timezone summary. A `.hermes` preview first requires
its backup password. Enter the exact destructive-confirmation phrase, provide
the destination instance's current master password and, for `.hermes`, retain
the separate backup password. Current financial and planning data is
replaced; the current owner credential and current session are retained, while
other sessions are ended. A checksum, strict schema and
references are checked before mutation. Table locks, one database transaction
and post-write domain checks guarantee that a failed restore leaves the old data
intact.
The UI and API reject outer backup requests larger than 72 MiB before parsing.
Plaintext JSON and decrypted payloads remain limited to 50 MiB.
The SHA-256 digest detects accidental corruption but is not an authenticity
signature, so only restore files from a trusted source.

Restore accepts `hermes-json-backup` schema 1 and `hermes` envelope version 1
containing payload schema 1. Unknown Hermes versions are rejected explicitly.
The scheduling payload preserves one-off plan origin, status and the link to an
applied actual operation alongside recurring rules and occurrences.

## Interim PostgreSQL backup

Choose a protected host directory with enough space, then run:

```bash
docker compose exec -T postgres sh -c \
  'pg_dump --format=custom --create --clean --if-exists \
  --username="$POSTGRES_USER" "$POSTGRES_DB"' > hermes.dump
```

Protect `hermes.dump` like the live financial database. Record the app commit or
version, PostgreSQL image version and backup time. Copy it to separate protected
storage and test restoration periodically.

## Interim PostgreSQL restore

Restore **overwrites the database named in the dump**. Verify the target Compose
project and backup file first, take another backup if possible, and stop the app:

```bash
docker compose stop app
docker compose exec -T postgres sh -c \
  'pg_restore --clean --if-exists --create --dbname=postgres \
  --username="$POSTGRES_USER"' < hermes.dump
docker compose start app
```

Then inspect logs and verify `/api/v1/health`. A successful health response does
not prove financial correctness; future restore verification must include schema
version and domain-level counts/invariants.

## Implemented portable restore behavior

1. Enforce the outer size limit and read the explicit format/version.
2. For Hermes V1, validate all KDF and encoded-field limits before Argon2id,
   decrypt the wrapped DEK, and authenticate/decrypt the payload.
3. Reject unsupported, malformed or unauthenticated input before mutation.
4. Validate all module data and exact decimal representations.
5. Restore all module state inside one database transaction.
6. Recheck cross-module invariants and commit once; roll back everything on any
   failure.
7. Import no source authentication state. Initialized restore preserves the
   destination credential/current session and ends other sessions; first-run
   restore creates a new destination credential/session in the restore
   transaction.

## Fund release compatibility (migration 0016)

Migration `0016_fund_release` adds the `fund_release` event label without
rewriting existing financial data. Schema-1 exports include these events via the
existing fund ledger and causal-operation field. Restore validates a single
negative fund movement, no reserve movements on the release itself, and exact
source/amount/date/description correspondence for an optional linked transfer.
Use the same or newer application to restore a backup containing release events;
older validators do not understand this event type.

Downgrade to 0015 refuses while release facts exist rather than deleting them.
If unused, downgrade keeps the enum label, consistent with 0013. For rollback
after using the feature, restore a separately verified pre-upgrade backup to an
isolated older instance; do not discard financial history to force downgrade.
