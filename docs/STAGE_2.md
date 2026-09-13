# Stage 2: application services

This draft builds on the unmerged stage-one foundation. It adds trusted Python application services, not HTTP endpoints or a browser UI. Construct Notebook only with an actor ID resolved by a trusted authentication layer; never use an actor supplied in a client request body.

## Implemented

- Create/list/rename projects; automatic Inbox remains the default even after rename.
- Create/read/edit/move notes and browse active/trash collections by project or explicit all-project scope.
- View revisions and restore historical content as a new revision without changing project membership.
- Trash/restore with retained history.
- Changed-only revisions, expected-version conflicts and seven-day successful retry receipts.
- Atomic revision, membership, audit and receipt writes under a SQLite write transaction.
- Input allowlists, UUID validation and owner checks.

## Internal interface

Notebook.execute accepts an operation name, UUID idempotency key and allowlisted keyword fields from the capability specification. Result IDs currently use the internal key id; transport adapters will map this to note_id/project_id. Actor attribution is server-derived. Returned receipt results contain IDs/version metadata rather than bodies.

Collection methods require explicit project scope (None for all projects), bounded limits and an after-ID continuation. This draft uses ID ordering for internal traversal. The later HTTP/UI adapter must add the specified recent-update/revision ordering and opaque scope-bound cursors before claiming the public collection contract complete.

## Verification and next work

Run pytest -q. Tests cover changed/no-op saves, restores, scope isolation, retries, concurrent edits, duplicate concurrent requests and injected rollback failures, in addition to foundation tests.

Browser login, authenticated transport adapters, opaque cursors, FTS/search, exports and the editor remain later work. No AI scope adapter exists. Readiness still targets migration 0001 because this stage does not change schema. Operational database errors in mutation services become temporarily_unavailable; unexpected integrity errors surface for diagnosis without committing partial state.
