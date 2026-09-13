# Stage 4: scoped full-text search and history usage

This draft builds on the authenticated Stage 3 browser notebook. It adds rebuildable SQLite FTS5 search over current active note content and exposes retained revision usage. Exports, backup/restore tooling, history cleanup and AI remain later work.

## Implemented

- Migration `0002` creates a `unicode61` FTS5 table and backfills all active notes from their current revisions.
- Changed note content, historical restores, trash and restore update FTS in the same SQLite write transaction as canonical note state, audit events and retry receipts.
- Search is project-scoped by default; explicit All Projects mode is supported. Trashed notes and historical-only text are excluded.
- User text is normalized into literal whitespace-separated terms combined with AND. Raw FTS syntax is never accepted. Queries are limited to 500 UTF-8 bytes and 32 terms.
- Results use BM25 relevance with title weighting, then `updated_at DESC` and note ID tie-breaking.
- Search cursors bind to project scope and a SHA-256 fingerprint of the normalized query. They are opaque convenience state, never authorization tokens.
- Browser search is submitted with Enter/Search and retained in the URL rather than requested on each keystroke.
- FTS snippets use fixed internal hit markers; browser rendering escapes note text before converting only those markers to `<mark>` elements. The JSON API returns plain marker-free snippets.
- `notes rebuild-search` reconstructs the derived index atomically from active current revisions.
- Per-note and workspace history usage report revision count and approximate UTF-8 title/body bytes. Per-note usage appears in History; workspace totals are API/service-only for now.

## Interfaces

`Notebook.search_notes(project_id, query, limit, after)` uses a project UUID or `None` for explicit all-project access. `Notebook.get_history_usage(note_id=None)` returns `revision_count` and `approximate_content_bytes`.

Authenticated transport endpoints are:

- `GET /api/search?project_id=<uuid|all>&q=<query>&limit=<n>&cursor=<opaque>`
- `GET /api/history-usage`
- `GET /api/notes/{note_id}/history-usage`

A blank browser query falls back to normal active-note listing. Search is intentionally unavailable for trash in this stage.

## Recovery and limitations

FTS is derived data, not another source of truth. `notes rebuild-search` deletes and reconstructs it inside one serialized transaction. Readiness now expects migration `0002`; it does not perform an expensive index-content audit on every health request.

Search v1 has no stemming, typo correction, fuzzy matching, phrase/OR syntax, saved filters, historical search, trash search, semantic/vector retrieval or AI behavior. Approximate history bytes are retained title/body payload only, not physical SQLite size, FTS overhead, audit/session storage or future attachments. No history cleanup action exists.
