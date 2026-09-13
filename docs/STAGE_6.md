# Stage 6: verified SQLite backup and recovery

This stage builds on Stage 5 portable exports and adds administrator-only disaster-recovery tooling for the complete retained SQLite application state. Backup/recovery is intentionally separate from browser exports: exports preserve selected current content, while backups preserve users, projects, active/trash state, retained revisions, audit state, retry receipts and derived FTS state.

## Implemented

- `notes-recovery backup DESTINATION` creates a transactionally consistent copy of the live file-backed SQLite database using SQLite's backup API rather than copying a live database/WAL set.
- Existing destinations are refused by default; `--overwrite` is required to replace a prior backup.
- Every successful backup is verified and reports a SHA-256 digest plus schema/project/note/revision counts.
- `notes-recovery verify-backup SOURCE` checks SQLite integrity, foreign keys, expected application tables, Alembic version, current-revision ownership, project ownership and one stable Inbox per owner.
- `notes-recovery restore SOURCE` restores into the configured SQLite target. An existing target requires `--confirm-replace` and the application must be stopped.
- Confirmed replacement first creates a timestamped pre-restore safety backup of the target.
- Restore uses SQLite's backup API rather than row-by-row reconstruction or an unsynchronized file copy.
- All restored sessions are revoked by default so recovery requires a fresh login; password hashes and other retained state remain preserved.
- Recovery tests restore into a separate database and verify project/Inbox identity, membership, active/trash lifecycle, retained history, current revision IDs, login, session revocation and FTS rebuild equivalence.
- No browser backup/restore surface, automatic schedule, retention rotation or backup encryption is introduced.

## Commands

Create and verify a backup:

```sh
notes-recovery backup /safe/path/local-ai-notes-backup.sqlite
notes-recovery verify-backup /safe/path/local-ai-notes-backup.sqlite
```

Replacing an existing backup requires explicit intent:

```sh
notes-recovery backup /safe/path/local-ai-notes-backup.sqlite --overwrite
```

Restore is an offline administrator operation. Stop the application first, then restore. Replacing an existing configured database requires explicit confirmation:

```sh
notes-recovery restore /safe/path/local-ai-notes-backup.sqlite --confirm-replace
alembic upgrade head
notes rebuild-search
```

The backup source is never migrated in place. If a future application version expects a newer schema, restore the captured database first and run normal Alembic migrations against the restored target before restarting the application.

## Verification model

Backup verification treats canonical relational state as essential and FTS contents as rebuildable derived state. It therefore validates SQLite/application invariants but does not make exact FTS row equivalence a prerequisite for recovery. The recovery acceptance test rebuilds FTS after restore and confirms equivalent search results.

The SHA-256 digest is informational and can be recorded when copying a backup to another device. No sidecar checksum file is created automatically.

## Operational boundaries

Backup files contain the complete notebook database, including note content, password hashes, trash and retained history. Protect them like the live database. Stage 6 does not add application-level encryption or automatic backup retention/rotation.

The live database must remain on local storage with SQLite locking semantics; do not run the active database over SMB. For meaningful hardware-failure protection, store backup copies on another physical device or storage target rather than only beside the live database.

Stage 6 does not perform a production restore or Pi deployment. ARM64/OMV/Tailscale validation and the broader v0.0.1 usability/accessibility acceptance pass remain separate work.
