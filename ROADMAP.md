# Roadmap

This roadmap communicates direction, not delivery dates.

## Phase 0 — Foundation (current)

- Finalize architecture and MVP specification.
- Record major choices as ADRs.
- Define data model, threat model, and capability contracts.
- Establish linting, tests, CI, and contribution conventions.

## Phase 1 — Non-AI vertical slice

- FastAPI application and migration framework.
- Authentication and responsive shell.
- Notes, revisions, trash/restore, and FTS5 search.
- Portable note export.
- Docker Compose development and Pi deployment documentation.

## Phase 2 — Note platform MVP

- Notebooks, tags, properties, links/backlinks, and attachments.
- Import workflows, backup guidance, and admin health view.
- Accessibility, security, migration, and recovery testing.

## Phase 3 — Optional AI boundary

- Durable idempotent jobs and authenticated worker API.
- Replaceable AI-provider interfaces.
- Proposed-output review flow and detailed provenance.
- First summarization/extraction evaluation set.

## Phase 4 — Multimodal knowledge assistance

- OCR, PDF/image ingestion, and transcription.
- Embeddings, hybrid retrieval, and grounded answers.
- Controlled capability tools and AI activity history.

## Phase 5 — Advanced portability and automation

- Carefully scoped offline/PWA capabilities.
- MCP adapter if justified.
- Opt-in training/evaluation export and local fine-tuning experiments.

## Not scheduled

CRDT sync, real-time collaboration, a graph database, arbitrary block databases, and autonomous destructive actions remain deferred until concrete requirements justify them.
