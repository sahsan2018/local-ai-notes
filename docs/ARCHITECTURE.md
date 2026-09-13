# Architecture

Status: Draft  
Last updated: 2026-09-13

## 1. Purpose

Local AI Notes is a local-first note platform. Ordinary note-taking is the product foundation; AI is an optional client of controlled application capabilities.

## 2. Architectural invariants

1. Human-owned information remains recoverable without AI.
2. Original input is never silently destroyed by AI processing.
3. Every AI modification is attributable and recoverable through retained history; future explicit history cleanup must disclose its recovery limits.
4. Canonical data is separated from regenerable derived data.
5. UI and AI actions use the same application capability layer.
6. Models, prompts, storage locations, and hardware are replaceable.
7. The application remains useful while every AI service is offline.
8. Personal deployment configuration never becomes a source-code assumption.
9. Project-scoped AI access is enforced by backend capabilities across retrieval and tools, never by prompts alone.

## 3. System context

```mermaid
flowchart TB
    Client["Responsive web client"] --> App["Pi application"]
    App --> DB["SQLite + FTS5"]
    App --> Files["Attachment storage"]
    App --> Queue["Durable job queue"]
    Worker["Optional GPU worker"] --> Queue
    Worker --> Provider["Replaceable AI provider"]
```

The web application, database, and attachment store form the core system. The remote worker and model provider are optional.

## 4. Initial technology direction

- FastAPI application with Pydantic validation and SQLAlchemy persistence.
- SQLite with FTS5 as the initial system of record and lexical search engine.
- Alembic migrations from the first schema.
- Server-rendered, progressively enhanced responsive UI; HTMX is the initial candidate.
- Docker Compose deployment on Raspberry Pi OS/OMV storage.
- Tailscale for private network reachability, plus application authentication.
- A SQLite-backed job queue before introducing Redis or a dedicated broker.

These are design directions, not irrevocable choices. Significant changes require an architecture decision record.

## 5. Canonical and derived data

SQLite is authoritative for notes, accepted metadata, revisions, relationships, jobs, and audit records. Attachments are files referenced by stable database identifiers.

Initial canonical note bodies use versioned Markdown with a small formatting toolbar; richer structured documents require a later schema decision and lossless native export. Display preferences are separate from saved styling. Opaque editor HTML is not authoritative. Markdown, JSON, and CSV are export formats rather than a second writable source of truth.

Derived data includes embeddings, vector indexes, thumbnails, cached summaries, OCR indexes, and saved query caches. Derived artifacts must be rebuildable from canonical records and retained source material.

## 6. Identity, history, and provenance

- Notes, revisions, attachments, jobs, tags, and other durable objects receive stable UUID-compatible IDs.
- Substantive changes create immutable revisions.
- Deletes are soft and restorable by default.
- Mutations record actor type, actor ID where applicable, origin, timestamp, and correlation/request ID.
- Imported, photographed, dictated, clipped, or scanned material retains its source artifact and extraction lineage.

## 7. Capability layer

Business operations are ordinary application services. The long-term catalog includes:

- notes: create, read, update, append, archive, restore, move, duplicate;
- organization: projects first, then folders within projects, tags, properties, links and backlinks;
- retrieval: FTS search, filters, saved queries;
- attachments and exports;
- revision history and comparison.

Routes and UI handlers call these services. Future REST tool adapters and MCP adapters wrap the same services. Models receive no direct SQL or arbitrary filesystem access.

Capabilities will declare a risk class: read-only, reversible write, significant/bulk write, or destructive. Bulk and destructive operations require preview and/or explicit confirmation.

## Project organization and AI scope

Each note belongs to exactly one owner-owned project. Bootstrap creates an Inbox project for quick capture. v0.0.1 supports creating, renaming and listing projects, moving active notes, project-scoped search/listing and explicit all-project browsing. Projects are not deleted in this milestone. Moves preserve content history, increment note version and create audit events. Later folders are subordinate to projects, not an alternative ownership model.

Future AI conversations bind to an explicit project scope. Authorization and scope filtering apply before retrieval results enter prompts and on every tool read/write, attachment access, cached result and citation lookup. Direct IDs and links must not bypass scope. Global scope is an explicit user choice; switching projects starts a fresh conversation by default, without inherited transcripts, summaries or retrieval caches.

Jobs capture scope and input revision IDs. Revalidate project membership before dispatch and again before accepting results or applying writes; moving a note can make a queued result stale. Already-disclosed model context cannot be retroactively erased, so revoke/restart affected conversation context before reuse. Project instructions are future configuration, not authorization rules.

Isolation limits application-supplied private context, not pretrained general knowledge. A future project-sources-only answer mode requires citations and an insufficient-evidence response when sources cannot support an answer. Projects are not separate user accounts or cryptographic storage boundaries.

## 8. Ingestion and AI boundary

Typed text is the first input adapter. Images, PDFs, handwriting OCR, audio transcription, and web clips later converge into the same ingestion pipeline.

AI access is isolated behind provider interfaces for structured generation, chat, embeddings, vision, and transcription. Provider configuration uses environment or secret storage, not committed values.

Jobs are durable and idempotent, with stable IDs, deduplication keys, status, attempts, timestamps, leases, result references, and error details. Workers claim jobs over an authenticated interface and return structured results for validation before mutation.

## 9. AI provenance and future training

When AI integration begins, retain:

- raw input and source references;
- retrieved context and its identifiers;
- model, model revision, quantization, provider, and inference settings;
- prompt and tool-schema versions;
- proposed output and tool calls;
- validation results, user decision, user edits, and final accepted result;
- latency, failures, and correlation IDs.

Training/evaluation exports must be explicit, reviewable, and privacy-aware. User content is never uploaded or published by default.

## 10. Security and privacy

- Tailscale is a network boundary, not the sole authentication mechanism.
- Authorization is enforced in application services as well as routes.
- State-changing requests use CSRF defenses where applicable.
- Uploads receive type, size, path, and malware-aware validation.
- Rendered Markdown and imported content are sanitized.
- Secrets and personal deployment details remain outside Git.
- Logs avoid note bodies, prompts, credentials, and attachment contents by default.
- Backups are encrypted where practical and restoration is tested.

See [SECURITY.md](../SECURITY.md) for reporting policy. A detailed threat model will precede remote AI write operations.

## Initial defaults and future maintenance

The first milestone uses one owner account, local bootstrap/password recovery, seven-day absolute sessions, explicit saves and preserved in-browser drafts on save failure. It does not promise offline synchronization or drafts surviving browser closure.

All saved revisions are retained in v0.0.1, with unchanged saves skipped and history counts/approximate bytes visible. Checkpoints and preview/confirmed cleanup belong to a later maintenance milestone; no pruning service or checkpoint table is required initially. The future retention policy is described in [Data model](DATA_MODEL.md). Evaluate storage growth before heavy use.

## 11. Operations and durability

Backup, export, and sync are separate systems. Initial deployment supports backups and exports; multi-device offline synchronization is deferred.

The application exposes health/readiness checks and structured logs. Operational state will eventually cover migrations, storage availability, backup recency, queue depth, worker connectivity, and index status.

## 12. Explicitly deferred

- CRDT or offline multi-writer synchronization;
- full event sourcing;
- graph databases and broad entity ontologies;
- dedicated vector databases;
- Redis/Celery-class queue infrastructure;
- MCP as an internal architectural dependency;
- arbitrary Notion-style block databases;
- autonomous destructive AI operations.

## 13. Proposed repository boundaries

```text
src/local_ai_notes/
  api/             HTTP routes and schemas
  application/     capabilities and orchestration
  domain/          core rules and types
  infrastructure/  persistence, files, providers
  web/             templates and static assets
tests/
docs/adr/
migrations/
```

This structure is provisional until the first vertical slice tests it.
