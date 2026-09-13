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
- A note result contains note_id, current_revision_id, revision_number, version, project_id, title, content format/version, body, created_at, updated_at and deleted_at.
- Lists default to 25 results, maximum 100, with opaque cursors and stable ID tie-breaking.
- History metadata is paginated; full historical bodies are retrieved individually.
- Ownership applies equally to reads, search, history and exports. Inaccessible object IDs return not_found without confirming existence.
- Trashed notes may be read in an explicit trash context, but cannot be edited.

## Read capabilities

| Operation | Inputs | Output |
| --- | --- | --- |
| list_projects | cursor, limit | Owned project IDs, names, descriptions and versions |
| get_project | project_id | Owned project metadata |
| export_project | project_id | Active-note snapshot plus project manifest |
| get_note | note_id, explicit lifecycle context | Current note |
| list_notes | scope, active or trash, cursor, limit | Summaries ordered updated_at descending then ID |
| search_notes | scope, query, cursor, limit | Active-note matches with safe snippets |
| list_revisions | note_id, cursor, limit | Revision metadata |
| get_revision | note_id, revision_id | Historical content and provenance |
| get_history_usage | optional note_id | Revision count and approximate title/body bytes |
| export_note | note_id | Captured Markdown revision |
| export_workspace | explicit all_projects, active notes | Snapshot-consistent archive and manifest |

Search v1 treats user input as literal word terms combined with AND, parameterizes the query and escapes FTS syntax. It does not expose raw FTS expressions or SQL. Blank search falls back to listing; missing matches return an empty page. Snippets must not inject unsafe HTML.

Collection operations require an explicit project_id or scope=all_projects. UI defaults to the selected project; global browsing is explicitly selected. Cursors bind to owner, scope, query and lifecycle. Direct-note operations validate supplied project scope against current membership. Future AI adapters always supply server-bound scope, including direct-ID and historical reads.

## Write capabilities

| Operation | Inputs | Behavior |
| --- | --- | --- |
| create_project | name, optional description, key | New owned project and audit event |
| rename_project | project_id, expected_version, name, key | Update name/version; audit event |
| move_note | note_id, expected_version, destination_project_id, key | Membership/version change; no content revision |
| create_note | optional project_id, optional title, body_markdown, idempotency_key | Note at version 1 and revision 1 |
| update_note | note_id, expected_version, title, body_markdown, key | New revision and incremented version if changed |
| trash_note | note_id, expected_version, key | Set deleted_at and increment version; audit only |
| restore_note | note_id, expected_version, key | Clear deleted_at and increment version; audit only |
| restore_revision | note_id, revision_id, expected_version, key | New current snapshot; preserve source and displaced history |

Lifecycle mutations already in the requested state are no-ops after matching the version. Replayed successful requests return the original result before checking the now-changed version. Historical restoration always creates a revision. No permanent note deletion exists in this milestone.

Checkpoint and cleanup capabilities are deferred to a later maintenance milestone. v0.0.1 retains all saved history and exposes only usage counts/approximate bytes. Later cleanup must preview/revalidate eligible IDs, require confirmation and protect restore/training dependencies; it must not be exposed as autonomous AI tooling.

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
5. Apply content/lifecycle/project changes.
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
| validation_error | 422 | Invalid fields or unsupported format |
| payload_too_large | 413 | Input exceeds configured limit |
| temporarily_unavailable | 503 | Database busy or storage unavailable |

Authorized version-conflict responses include current version/revision ID. The UI preserves its unsaved draft and offers latest content for manual reconciliation. It must never automatically resubmit replacement content with an updated version.

## Retry contract

Retain successful receipts for at least seven days. Store only necessary result identifiers/state, not full note bodies. Same actor/key/payload within that window returns the original outcome. New edits use new keys.

After expiry, clients must reconcile current state before retrying, especially create_note, which has no existing expected version. Never promise indefinite exactly-once execution. The initial client does not maintain an offline retry queue.

Authorization and current lifecycle access are still checked before returning a cached receipt; replay does not grant access to deleted/pruned historical content.

## Validation and rendering

Proposed initial limits: title 200 Unicode characters; Markdown body 1 MiB UTF-8. Permit an empty body; normalize omitted or blank titles to Untitled before hashing and saving. Limits are configurable and tested, not silently truncated.

Normalize CRLF to LF. Otherwise preserve content including whitespace. v0.0.1 supports headings, emphasis, lists, quotes, code and safe links. Raw HTML is not executed; unsafe URL schemes are rejected by rendering. No inline remote images or attachment uploads in this milestone. Content must remain safely escaped in previews and snippets.

## Authentication capabilities

Local create_owner creates one password-hashed account and refuses a second owner. Login issues a random opaque session token with only its hash stored; logout revokes it. Use HttpOnly cookies, SameSite policy and Secure cookies for HTTPS deployment, CSRF defense on browser writes, and login rate limiting. Sessions expire absolutely seven days after issue. A local administrator password-recovery command revokes all existing sessions. Select and document the password hashing implementation during security review.

## Export contract

Use UUID-based filenames. Serialize YAML frontmatter properly with format version, note/revision IDs, title and timestamps. Workspace export captures all active notes in one consistent read snapshot; manifest lists note IDs, filenames, revision IDs, project membership, project names/IDs (including empty projects), Inbox identity and export schema version. Project export includes only the selected project. Complete the snapshot read before streaming to a slow client.

Exports do not include sessions, credentials or full history. History cleanup does not modify existing exports or backups. Future rich-document exports must report lossy Markdown conversion and offer lossless native JSON.

## Future extension rules

Tool adapters declare risk and approval requirements; reversible does not mean automatically approved. Rich formatting, images, OCR and AI require new versioned contracts. User display preferences do not call update_note; persistent per-note document styling does.

## Project mutation details

Names are nonblank and at most 200 characters; descriptions at most 2,000. Duplicate names are allowed; IDs identify projects. Bootstrap creates Inbox; absent project_id on create_note resolves to that stable Inbox ID before canonical payload hashing. Invalid explicit project IDs fail, never silently fall back.

Moves require an active note and owned destination. A same-project move is a no-op after matching expected_version. Record source and destination IDs; increment note version/updated_at but preserve current_revision_id. Revision restore changes content only, never membership. No project deletion/archive or moving trashed notes exists initially. Rename checks project version and leaves note content/version unchanged.

Future AI project scope restricts both source and destination of a move. Crossing scope requires a separately authorized scope change, not model-supplied arguments. Jobs store scope and input revision IDs, revalidate membership on dispatch/completion and reject stale writes. Searches filter before results enter prompts; caches and citations are scope-aware. Switching scope starts a fresh conversation by default. Project-source-only mode requires evidence citations and insufficient-evidence behavior, not a promise of removing model general knowledge.
