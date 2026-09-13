# ADR-0002: Projects and first-milestone boundaries

- Status: Accepted
- Date: 2026-09-13
- Decision owners: project owner

## Context

Notes need lightweight organization now and selectable private-data scope for future AI. Retention cleanup had expanded the initial milestone beyond the core notebook. Rich editing needs a deliberate evolution path.

## Decision

Use one project per note with automatic Inbox. Include project creation/rename/listing, moves, scoped listing/search and explicit global browsing in v0.0.1. Defer nested folders and project deletion. Preserve note identity/content history on moves, increment concurrency version and audit membership.

Future AI scope is enforced by backend retrieval and capabilities, including direct IDs, attachments, caches and citations. Global scope is explicit. Default to fresh conversations on scope changes and revalidate queued jobs. Scope limits supplied private data, not pretrained knowledge; source-only answers need grounding/citations.

Include a small Markdown toolbar now. Retain all saved revisions initially, skip unchanged saves and show history usage. Defer checkpoints and confirmed cleanup to maintenance work after measuring growth. Reserve content format/schema versions for later structured rich documents; keep display preferences separate. This refines ADR-0001's initial Markdown choice without changing SQLite authority.

## Consequences

Project membership and export metadata are designed early. Scope enforcement must remain separate from authorization and cannot rely on prompts. History grows until explicit maintenance is implemented. Rich text/image editing remains a later core feature rather than an AI prerequisite.

## Alternatives considered

- Nested folders first: more hierarchy and UI complexity than initial needs.
- Many-to-many project membership: ambiguous AI context boundaries; deferred.
- Prompt-only scope: does not enforce access.
- Cleanup in first milestone: destructive maintenance distracts from persistence and editing.
