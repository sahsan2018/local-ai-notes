# Product Specification

Status: Draft  
Last updated: 2026-09-13

## Product statement

Local AI Notes is a responsive, self-hosted note-taking application that protects ownership and portability of personal information while making local AI assistance optional, transparent, and controllable.

## Target users

The initial user is a technically capable self-hoster using desktop and mobile browsers. The architecture should remain suitable for broader public use without encoding one person's devices, paths, or Tailnet.

## Core experience

Desktop uses a three-pane workspace: navigation, note/editor, and contextual metadata. Mobile presents these as focused screens. AI remains accessible but does not dominate the interface.

## MVP (v0.1)

A user can:

- authenticate;
- create, view, edit, and archive/restore notes;
- organize notes in notebooks/folders;
- add tags and simple typed properties;
- link notes and inspect backlinks;
- attach files;
- search titles and bodies with FTS5;
- view revision history and restore an earlier revision;
- export a note or workspace in documented portable formats;
- use the essential interface on desktop and mobile.

AI is not an MVP acceptance criterion.

## First AI vertical slice

- The Pi creates a durable summarization job.
- An authenticated remote worker claims it and invokes a configured local provider.
- The proposed summary records full AI provenance.
- The user may accept, edit, or reject it.
- Acceptance creates a normal attributed revision.
- The core app continues working if the worker is unavailable.

## Later core features

- tasks and due dates;
- saved filtered/sorted views;
- Markdown/JSON/CSV import;
- PWA installation and limited offline capture;
- richer relationships and entity records;
- backup/status administration.

## Later AI features

- OCR and handwriting ingestion;
- audio transcription;
- automatic organization and metadata suggestions;
- embeddings and hybrid retrieval;
- grounded conversational search with citations;
- controlled multi-step tool use;
- evaluation suites and opt-in training-data export.

## Non-goals for early releases

- pixel-for-pixel cloning of another note application;
- unrestricted model access to SQL or files;
- mandatory cloud accounts or cloud AI;
- real-time collaborative editing;
- autonomous bulk deletion;
- replacement of source artifacts with generated text.

## MVP quality requirements

- Responsive at common phone and desktop widths.
- Keyboard-accessible primary workflows and semantic HTML.
- Tested migration and restore procedures.
- No secrets or personal infrastructure identifiers in source.
- Deterministic export of canonical content.
- Meaningful errors when storage or optional services are unavailable.

## Open product decisions

- editor library and exact Markdown subset;
- notebook hierarchy versus labels at the domain level;
- property types included in v0.1;
- attachment size/type policy;
- authentication mechanism for the first self-hosted release;
- exact import/export compatibility promises.
