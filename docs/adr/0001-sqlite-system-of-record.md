# ADR-0001: Use SQLite as the initial system of record

- Status: Accepted
- Date: 2026-09-13
- Decision owners: project maintainers

## Context

The application needs durable note storage, revision history, relationships, full-text search, and reliable operation on a Raspberry Pi. A writable Markdown vault plus a separate metadata database would introduce synchronization conflicts and unclear authority.

## Decision

SQLite is the initial authoritative store for notes, accepted metadata, revisions, jobs, and audit records. Attachments remain files referenced by stable IDs. Note bodies use a Markdown-compatible representation. Markdown, JSON, and CSV are deterministic import/export formats, not a concurrently writable second source of truth. FTS5 provides initial search.

## Consequences

Transactions and migrations have one clear authority, while exports preserve portability. External editors cannot safely rewrite a live vault without an explicit future synchronization design. SQLite backup and restore procedures become critical. Derived indexes must remain rebuildable.

## Alternatives considered

- Markdown files as canonical data: highly portable, but concurrency, atomic cross-note changes, revision metadata, and synchronization require substantially more machinery.
- PostgreSQL: capable but adds operational weight not justified for the initial single-user Pi deployment.
- Event sourcing: powerful auditability at the cost of complexity beyond current requirements.
