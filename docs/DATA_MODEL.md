# Data Model

Status: Proposed implementation specification
Scope: [v0.0.1](MILESTONE_0_0_1.md)
Related: [Architecture](ARCHITECTURE.md), [Capabilities](CAPABILITIES.md)

## Authority and scope

SQLite is the system of record. Current content lives in immutable revisions; notes point to their current revision. Exports and FTS5 are derived representations. The active database resides on a locally mounted Pi disk, never a client-accessed SMB database.

This document refines the broader architecture: immutable means revisions cannot be edited in place, not that every revision must be retained forever. History is recoverable while retained; approved retention cleanup may remove eligible history. No cleanup happens implicitly on save.

## Initial tables

All durable identifiers are UUIDs. Store UTC timestamps consistently. Enable foreign keys on every connection. Use Alembic migrations.

| Table | Fields and responsibilities |
| --- | --- |
| users | id, normalized unique username, password_hash, created_at; initial installation permits one owner |
| sessions | id, user_id, unique token_hash, created_at, expires_at, revoked_at; store only a digest of the session secret |
| projects | id, owner_id, name, description, is_inbox, version, created_at, updated_at |
| notes | id, owner_id, project_id, current_revision_id, version, next_revision_number, created_at, updated_at, deleted_at |
| note_revisions | id, note_id, revision_number, title, content_format, content_schema_version, body_markdown, actor_type, actor_id, source_type, request_id, created_at, restored_from_revision_id |
| audit_events | id, nullable note_id, nullable project_id, event_type, actor_type, actor_id, request_id, created_at, details_schema_version, details_json |
| mutation_receipts | actor_id, idempotency_key, operation, request_hash, result_json, created_at, expires_at; unique actor/key pair |

Seven initial tables include projects; revision_checkpoints is deferred.

## Project membership

Each note has one non-null project_id. Enforce matching ownership through a composite foreign key (owner_id, project_id) to projects(owner_id, id). Owner bootstrap creates exactly one Inbox in the same transaction; enforce one is_inbox row per owner with a partial unique index. Inbox identity is a flag and ID, not its display name. Renaming Inbox is allowed. Project names need not be unique; IDs distinguish them.

Project creation/rename updates project version and audit history. Use nonblank names up to 200 characters and optional descriptions up to 2,000 characters. Local bootstrap is atomic. No project deletion/archive, nested folders or cascade deletion in v0.0.1.

An active-note move validates destination ownership, checks expected note version, updates membership/version/updated_at and audits old/new project IDs atomically. No content revision is created. Moving to the existing project is a no-op after the concurrency check. Content revision restore does not change project membership. Trashed notes retain their project and cannot move until restored.

Project membership is canonical metadata, not copied into every body snapshot. Future folder IDs must belong to the same project as their note. Scope lookup uses current membership, including access to historical revisions; old audit project IDs do not authorize access.

## Content and identity

For v0.0.1, content_format is markdown and content_schema_version is 1. Titles and bodies exist only on note_revisions. notes.version increases for content and lifecycle mutations; revision_number increases only when a revision is created. Never reuse revision numbers after pruning; next_revision_number is monotonic.

A note's current revision must belong to that note. Enforce a composite relationship from (notes.id, notes.current_revision_id) to (note_revisions.note_id, note_revisions.id), with a unique parent key and a deferred foreign key to permit atomic creation. Also enforce the revision-to-note foreign key. Validate this circular insertion path in migration/integration tests.

Unique constraint: (note_id, revision_number). Index owner/lifecycle/update time for listing and note/revision number for history. The current revision pointer is non-null at transaction commit.

Server-controlled actor fields identify who acted; source_type describes how content originated. Initial source is manual. Future AI and OCR processing require dedicated run/source relations, not arbitrary client-supplied provenance.

## Revision semantics

Create a full title/body snapshot for each changed explicit save. Do not create revisions on keystrokes or identical saves. LF newline normalization is specified before equality checks; otherwise preserve whitespace.

History restore always creates a new revision, even if historical content equals current content, because the explicit restore itself is meaningful. Record the source revision and previous current revision. Trash/restore creates audit events but no content revision. Editing and historical restoration require an active note.

v0.0.1 retains every revision, including restoration source and displaced content. Record both IDs in audit details. Checkpoints/protection management are deferred until cleanup exists.

## Initial retention and future cleanup

Full text snapshots are simple and independently recoverable, but storage grows with saved content. Illustrative calculation: 1,000 notes times 100 revisions times 10 KiB is about 977 MiB of body data alone, before titles, indexes, database overhead and backups. This is arithmetic, not a workload forecast.

v0.0.1 retains all revisions and exposes counts/approximate bytes. No checkpoint table or cleanup operation is implemented initially. Review measured growth before heavy everyday use.

For a later maintenance milestone, the proposed cleanup policy per active note is:

- Always retain the current revision.
- Retain the original revision.
- Retain the latest 100 revisions.
- Retain all revisions from the last 30 days.
- Retain explicitly protected checkpoints and revisions required by restore lineage.
- Exclude trashed notes from this first cleanup implementation.

These rules form a union, not a hard 100-revision cap. Large or frequently edited notes can exceed it. The limits are configurable; defaults are product starting points subject to measured use.

The later maintenance milestone introduces owner-invoked preview and confirmed cleanup, not scheduled silent deletion. Preview reports exact candidate IDs, policy, and estimated payload bytes. Explain that deleting history is irreversible within the app and does not immediately shrink the SQLite file or remove older backup copies.

In that later milestone, deleting eligible snapshots is allowed only through the retention service. Preserve compact audit events with deleted revision IDs as historical identifiers; audit JSON must not have a foreign key requiring deleted rows. Protect every revision referenced by a retained restored_from_revision_id and recheck dependencies inside cleanup's transaction. Monotonic numbering makes gaps expected.

Return a conflict when note versions, checkpoints or retention candidates change after preview. Deleting content history is destructive and is never exposed as an autonomous AI tool. Ordinary editing and restore never trigger cleanup.

A simple storage summary reports revision count and approximate stored title/body bytes. This is not exact disk usage. Physical compaction, audit retention, and hard workspace quotas are future operations work. Saves must fail clearly and atomically when storage is exhausted.

## Future training data and retention

Do not keep every historical edit solely because it might be useful for training. Before AI ships, introduce explicit AI-run and reviewed-example records with model/prompt/tool versions, source and context, proposal, user decision and final result. Training retention must be opt-in and independently specified.

Future examples must either own an approved immutable snapshot or explicitly protect referenced revisions; pruning must not silently break them. No training data, prompts, or note bodies belong in ordinary logs or the public repository.

## Future rich text and images

Plain Markdown cannot preserve arbitrary font family, size, color, alignment and layout. A small Markdown toolbar is included initially without changing storage; a rich document editor requires a versioned structured-document schema and an ADR before implementation.

Reserve format/version fields now. Later migrations may add structured JSON content with exactly one authoritative representation per revision. Markdown and HTML become derived exports for that format; do not maintain two independently writable bodies. Rich exports must declare fidelity limits; native JSON is the lossless export.

Display-only preferences, such as editor font and reading width, belong to user settings, not note revisions. Per-note formatting belongs to the document.

Images are future attachment objects, not embedded base64 copies in every revision. Keep originals and reference immutable edited derivatives by stable IDs. Crop, rotation and annotations must retain source relationships; garbage collection must respect retained revisions and backups. Image attachment support does not imply a full image editor.

## Transactions and recovery

A content mutation commits the revision, pointer/version, FTS update, audit event and retry receipt together. Use an atomic expected-version comparison; do not rely on an earlier route-level read. SQLite busy/space failures must leave no partial state.

FTS indexes only active current titles/bodies and can be rebuilt. Session secrets and note content are excluded from operational logs. Backups preserve the complete retained database; exports preserve selected current content. Use a consistent SQLite backup operation, not an unsynchronized copy of a live database and WAL files.

Tests must cover foreign keys, circular initial insertion, concurrent saves, rollback on failure, retained lineage, project ownership/moves/scoped search and backup restoration. Pruning tests arrive with the later maintenance milestone.

## Session and export metadata defaults

Sessions expire absolutely seven days after issue; logout and local administrator password recovery revoke sessions. Successful mutation receipts persist at least seven days. Exports include project IDs/names and membership; workspace manifests include empty projects and Inbox identity for future import. Scoped exports omit unrelated projects. UUID filenames avoid title collisions.
