# Capability Contracts

Status: Proposed implementation specification
Scope: [v0.0.1](MILESTONE_0_0_1.md)
Data: [Data model](DATA_MODEL.md)

## Boundary

HTTP routes and UI handlers invoke application services. Services enforce ownership, validation, revision semantics, concurrency, and transactions. Future AI adapters invoke selected services through separate approval policy. No SQL or arbitrary filesystem paths are accepted.

Actor identity comes from authenticated server context. Public registration is disabled. Owner bootstrap is a local administrative operation, never an unauthenticated first-visitor claim.

## Common request and result rules

- IDs are UUIDs; all timestamps are UTC.
- Mutations carry an idempotency key; note mutations also carry expected_version.
- Correlation request IDs are server-issued or validated separately from idempotency.
- Response envelopes include request_id.
- A note result contains note_id, current_revision_id, revision_number, version, title, content format/version, body, created_at, updated_at and deleted_at.
- Lists default to 25 results, maximum 100, with opaque cursors and stable ID tie-breaking.
- History metadata is paginated; full historical bodies are retrieved individually.
- Ownership applies equally to reads, search, history, exports and cleanup. Inaccessible object IDs return not_found without confirming existence.
- Trashed notes may be read in an explicit trash context, but cannot be edited.

## Read capabilities

| Operation | Inputs | Output |
| --- | --- | --- |
| get_note | note_id, explicit lifecycle context | Current note |
| list_notes | active or trash, cursor, limit | Summaries ordered updated_at descending then ID |
| search_notes | query, cursor, limit | Active-note matches with safe snippets |
| list_revisions | note_id, cursor, limit | Revision metadata and checkpoint flags |
| get_revision | note_id, revision_id | Historical content and provenance |
| get_history_usage | optional note_id | Revision count and approximate title/body bytes |
| preview_revision_cleanup | note_id, retention policy | Exact candidates, estimated bytes and digest of observed state |
| export_note | note_id | Captured Markdown revision |
| export_workspace | active notes | Snapshot-consistent archive and manifest |

Search v1 treats user input as literal word terms combined with AND, parameterizes the query and escapes FTS syntax. It does not expose raw FTS expressions or SQL. Blank search falls back to listing; missing matches return an empty page. Snippets must not inject unsafe HTML.

Preview is computed on the server. Confirmation resubmits the candidate IDs and preview digest, which the server recomputes from authenticated, current state. Client-supplied IDs never independently authorize deletion.

## Write capabilities

| Operation | Inputs | Behavior |
| --- | --- | --- |
| create_note | title, body_markdown, idempotency_key | Note at version 1 and revision 1 |
| update_note | note_id, expected_version, title, body_markdown, key | New revision and incremented version if changed |
| trash_note | note_id, expected_version, key | Set deleted_at and increment version; audit only |
| restore_note | note_id, expected_version, key | Clear deleted_at and increment version; audit only |
| restore_revision | note_id, revision_id, expected_version, key | New current snapshot; protect source and displaced revision |
| protect_revision | note_id, revision_id, expected_version, key | Add checkpoint; increment note version if changed |
| unprotect_revision | note_id, revision_id, expected_version, key | Remove owner checkpoint; other retention protections still apply |
| apply_revision_cleanup | note_id, expected_version, candidate IDs, preview digest, explicit confirmation, key | Revalidate and delete only eligible snapshots; increment version and audit |

Lifecycle mutations already in the requested state are no-ops after matching the version. Replayed successful requests return the original result before checking the now-changed version. Historical restoration always creates a revision. No permanent note deletion exists in this milestone.

Cleanup is a destructive owner-only maintenance capability. It is not a normal note-edit action and is not available to AI. No scheduled cleanup exists in v0.0.1.

## Update example

~~~json
{
  "note_id": "a54ea987-79d5-43d4-af68-f85557f7a6c2",
  "expected_version": 5,
  "title": "Equipment troubleshooting",
  "body_markdown": "Channel 1 exhibits noise.",
  "idempotency_key": "a4bd6c28-1737-426c-84b6-3a062563d664"
}
~~~

Successful mutation result includes current_revision_id, revision_number, version, changed and updated_at. A no-op leaves revision/version/update time unchanged.

## Atomic mutation sequence

1. Authenticate and authorize.
2. Look up actor-scoped retry receipt.
3. Reject key reuse with a different operation or canonical payload.
4. Validate input, lifecycle and expected version inside the transaction.
5. Apply content/lifecycle/checkpoint/cleanup changes.
6. Update current pointer and FTS when relevant.
7. Append audit event and successful receipt.
8. Commit; return the committed result.

Use conditional version updates and handle competing inserts/receipts so duplicate requests cannot create duplicate mutations. Failed requests leave no successful receipt.

## Errors and transport mapping

| Code | HTTP | Meaning |
| --- | --- | --- |
| authentication_required | 401 | Missing/expired session |
| forbidden | 403 | Authenticated operation not allowed |
| not_found | 404 | Missing or inaccessible object |
| version_conflict | 409 | Stale expected_version |
| invalid_state | 409 | For example editing a trashed note |
| idempotency_conflict | 409 | Same key, different request |
| preview_stale | 409 | Cleanup state changed since preview |
| validation_error | 422 | Invalid fields or unsupported format |
| payload_too_large | 413 | Input exceeds configured limit |
| temporarily_unavailable | 503 | Database busy or storage unavailable |

Authorized version-conflict responses include current version/revision ID. The UI preserves its unsaved draft and offers latest content for manual reconciliation. It must never automatically resubmit replacement content with an updated version.

## Retry contract

Retain successful receipts for at least seven days. Store only necessary result identifiers/state, not full note bodies. Same actor/key/payload within that window returns the original outcome. New edits use new keys.

After expiry, clients must reconcile current state before retrying, especially create_note, which has no existing expected version. Never promise indefinite exactly-once execution. The initial client does not maintain an offline retry queue.

Authorization and current lifecycle access are still checked before returning a cached receipt; replay does not grant access to deleted/pruned historical content.

## Validation and rendering

Proposed initial limits: title 200 Unicode characters; Markdown body 1 MiB UTF-8. Permit an empty body; reject blank titles with an actionable message. Limits are configurable and tested, not silently truncated.

Normalize CRLF to LF. Otherwise preserve content including whitespace. v0.0.1 supports headings, emphasis, lists, quotes, code and safe links. Raw HTML is not executed; unsafe URL schemes are rejected by rendering. No inline remote images or attachment uploads in this milestone. Content must remain safely escaped in previews and snippets.

## Authentication capabilities

Local create_owner creates one password-hashed account and refuses a second owner. Login issues a random opaque session token with only its hash stored; logout revokes it. Use HttpOnly cookies, SameSite policy and Secure cookies for HTTPS deployment, CSRF defense on browser writes, and login rate limiting. Select and document password hashing and session expiry during implementation security review.

## Export contract

Use UUID-based filenames. Serialize YAML frontmatter properly with format version, note/revision IDs, title and timestamps. Workspace export captures all active notes in one consistent read snapshot; manifest lists IDs, filenames, revision IDs and export schema version. Complete the snapshot read before streaming to a slow client.

Exports do not include sessions, credentials or full history. History cleanup does not modify existing exports or backups. Future rich-document exports must report lossy Markdown conversion and offer lossless native JSON.

## Future extension rules

Tool adapters declare risk and approval requirements; reversible does not mean automatically approved. Rich formatting, images, OCR and AI require new versioned contracts. User display preferences do not call update_note; persistent per-note document styling does.
