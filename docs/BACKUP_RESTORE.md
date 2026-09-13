# Backup and Restore Runbook

This runbook covers the v0.0.1 SQLite recovery workflow. Portable Markdown/ZIP exports are not substitutes for backups: exports omit trash, full revision history, credentials, sessions and other application state.

## Safety rules

- Keep the active SQLite database on locally mounted storage, not SMB.
- Treat backup files as sensitive complete copies of the notebook.
- Prefer a backup destination on another physical disk/device for hardware-failure protection.
- Creating a backup may be done while the application is running.
- Restoring must be done with the application stopped.
- Never restore over an existing configured database without `--confirm-replace`.
- A confirmed replacement automatically creates a timestamped pre-restore safety backup of the old target.
- Restored browser sessions are revoked automatically; log in again after recovery.

## Local backup

With `DATABASE_URL` pointing at the live file-backed SQLite database:

```sh
notes-recovery backup /safe/path/local-ai-notes-backup.sqlite
```

A successful command prints the schema version, project/note/revision counts and SHA-256 digest. Record the digest if the backup will be copied elsewhere.

Verify an existing backup independently:

```sh
notes-recovery verify-backup /safe/path/local-ai-notes-backup.sqlite
```

The verifier checks SQLite integrity, foreign keys, required application tables, Alembic version, current revision relationships, note/project ownership and Inbox identity.

## Local restore

1. Stop the application process.
2. Verify the backup.
3. Restore into the configured `DATABASE_URL` target.
4. Run migrations against the restored target.
5. Rebuild FTS derived state.
6. Restart the application and log in again.

```sh
notes-recovery verify-backup /safe/path/local-ai-notes-backup.sqlite
notes-recovery restore /safe/path/local-ai-notes-backup.sqlite --confirm-replace
alembic upgrade head
notes rebuild-search
```

If the target database does not yet exist, `--confirm-replace` is not required. If it already exists, restore refuses to proceed without the flag.

## Docker named-volume backup

The base Compose file stores the application database under `/data` in the `notes-data` volume. Mount a separate host backup directory into a one-off container rather than writing backups only into the application volume.

Example pattern:

```sh
docker compose run --rm \
  -v /safe/host/backups:/backups \
  app notes-recovery backup /backups/local-ai-notes-backup.sqlite
```

Use a real host path appropriate for your system; personal deployment paths are intentionally not committed to the repository.

## Docker named-volume restore

Stop the stack first:

```sh
docker compose down
```

Then run a one-off container with both the application data volume and backup directory available:

```sh
docker compose run --rm \
  -v /safe/host/backups:/backups \
  app notes-recovery verify-backup /backups/local-ai-notes-backup.sqlite

docker compose run --rm \
  -v /safe/host/backups:/backups \
  app notes-recovery restore /backups/local-ai-notes-backup.sqlite --confirm-replace

docker compose run --rm app alembic upgrade head
docker compose run --rm app notes rebuild-search
docker compose up -d --wait
```

The restore command uses the container's configured `DATABASE_URL`, currently `sqlite:////data/notes.db`.

## OMV / Raspberry Pi notes

For the intended Pi deployment, the same commands apply when `/data` is an OMV-managed bind mount. Ensure the restored database remains readable and writable by the application user (currently UID 10001 in the container) and that the filesystem supports normal SQLite locking semantics.

Do not use a network SMB share as the active database location. A separate OMV disk or another host can be a suitable backup destination, provided it is mounted into the one-off recovery container only for the backup/recovery operation.

Actual ARM64/Pi recovery execution is part of the deployment acceptance pass and is not claimed by Stage 6 CI alone.

## What recovery preserves

A full backup preserves the complete retained database at its captured point in time, including:

- owner identity and password hash;
- projects and stable Inbox identity;
- active and trashed notes;
- project membership;
- current revision pointers and all retained revision snapshots;
- audit events and mutation receipts;
- schema version and current FTS data.

On restore, existing sessions from the backup are revoked deliberately. FTS is treated as derived state and should be rebuilt after recovery even though it is present in the copied database.

## What this stage does not automate

There is no scheduled backup service, retention rotation, cloud upload, backup encryption, attachment bundle, or browser restore button. The CLI primitives are suitable for later scheduling with cron, systemd timers, OMV scheduled tasks or another administrator-controlled mechanism.
