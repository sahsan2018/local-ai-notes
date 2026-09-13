# Milestone v0.0.1: Trustworthy Personal Notebook

Status: Proposed acceptance specification; no implementation claimed
Related: [Product specification](PRODUCT_SPEC.md), [Data model](DATA_MODEL.md), [Capabilities](CAPABILITIES.md)

## Goal and relationship to v0.1

Deliver a usable single-owner notebook from desktop and mobile with explicit saves, safe conflicts, search, retained history, trash and export. This is smaller than the broader v0.1 MVP. Local-first initially means self-hosted ownership; offline editing and synchronization are not promised.

## Included

- Local owner bootstrap, login/logout and protected content.
- Create/rename/list projects, automatic Inbox, active-note moves and a project selector; no project deletion.
- Project-scoped active/trash lists and explicit all-project browsing.
- Markdown editor with a small toolbar for headings, emphasis, lists, links, quotes and code, plus sanitized preview.
- Save button and Ctrl/Cmd+S; visible unsaved/saving/saved/failed states.
- Navigation warning for unsaved edits; no promise of unsaved crash recovery.
- Project-scoped current-content full-text search and explicit all-project search.
- Immutable saved revisions, historical viewing and restore-as-new-revision.
- Revision counts and approximate history payload size.
- Note Markdown export and active-workspace archive/manifest export.
- Persistent Docker storage, health checks, migrations and backup/restore instructions.
- Responsive layout and keyboard-accessible primary workflows.
- Core operation with all AI services off.

## Agreed operational defaults

One owner, local bootstrap and password recovery, no public registration. Seven-day absolute sessions; logout/recovery revoke sessions. Seven-day minimum mutation receipt retention. Lists default to 25, maximum 100. Titles allow 200 characters; omitted/blank titles become Untitled. Bodies allow 1 MiB UTF-8 and may be empty. No permanent deletion or trash expiration. Manual consistent backup and tested restore initially. Failed saves keep drafts in the open editor, without promising persistence after browser closure.

## Revision policy

Unchanged saves create no revision. Changed explicit saves create independent full snapshots. No autosave revision flood.

All saved revisions are retained initially. Show revision counts and approximate payload bytes; review actual growth before heavy everyday use. Checkpoints, preview/confirmed cleanup and their race/dependency handling move to a later maintenance milestone. The proposed future policy in [Data model](DATA_MODEL.md) is not an active v0.0.1 retention limit. Storage failures must leave committed content intact and show the unsaved draft.

## Editor roadmap and fidelity

| Capability | v0.0.1 | Later direction |
| --- | --- | --- |
| Headings, bold, italic, lists, quotes, code, links | Markdown toolbar, syntax and preview | Rich/visual editing |
| Font family, font size, text color | Not supported as saved note styling | Versioned rich document model |
| Alignment and per-note layout | Not supported | Rich editor evaluation and schema decision |
| Reading width and editor display font | Basic responsive defaults | User preferences, separate from content |
| Inline images and attachments | Not included | Broader note platform work |
| Image crop, rotate, annotations | Not included | Optional editor preserving original plus derivatives |
| Offline editing and synchronization | Not included | Separate conflict/sync design |

Advanced rich text and image editing are future core product improvements, not AI dependencies. No particular editor library is selected. Do not promise arbitrary styling round-trips through Markdown. Reserve format/schema versions now; adopt structured JSON through a later ADR and migration when needed. Future lossless export is native structured data, with Markdown an explicitly limited portable alternative.

## Acceptance scenarios

1. Clean setup: documented Docker setup plus local bootstrap creates one owner; no default credentials or public registration.
2. Authorization: unauthenticated routes cannot expose notes, search, history, exports or another owner's project.
3. Save: a new note receives stable identity and initial revision; reopening returns exact normalized content.
4. No-op: saving unchanged current content preserves version, revision count and modified time.
5. Conflict: two sessions open one version; after one saves, the other receives conflict and keeps its unsaved text.
6. Retry: repeating a successful request key/payload creates no duplicate note/revision; changed payload with the same key is rejected.
7. History: each changed save appears once; restoring old content creates a new revision and preserves restoration context.
8. Trash: trash removes notes from normal lists/search; restore returns them; trashed notes cannot be edited.
9. Search: only current active content matches; rebuild produces equivalent results.
10. Export: duplicate titles and unsafe filename characters cannot collide or escape archive paths; frontmatter round-trips through a YAML parser.
11. Workspace snapshot: concurrent editing during export cannot produce a mixture of snapshot states.
12. Persistence: restarting the container preserves notes, retained revisions and project membership.
13. Recovery: restore a consistent backup into a separate instance and verify notes, retained history, ownership and search rebuild.
14. Failure atomicity: simulated write/storage failure leaves no partial revision/pointer/audit changes; UI reports failure.
15. Security: script-like Markdown and unsafe links cannot execute; browser writes enforce CSRF protections.
16. Usability: main workflows work with keyboard, phone viewport and desktop viewport; focus and save status are understandable.
17. Independence: all above work while the GPU machine and AI provider are off.

## Project acceptance scenarios

- Bootstrap creates exactly one stable Inbox; default capture goes there even after rename.
- Create/list/rename projects and move active notes without changing revision IDs or content history.
- A stale move/save receives a conflict; moving a trashed note is rejected.
- Selected-project search/listing omits other projects; all-project access is explicit.
- Cross-owner project IDs cannot be used for note creation/moves or reads, even though the initial UI has one owner.
- Exports preserve project identity/membership, empty projects and duplicate titles; scoped export contains no unrelated project data.
- Revision restore leaves current project membership unchanged.
- Nested folders, project deletion and actual AI behavior are not implemented; future AI scope isolation is documented in [Architecture](ARCHITECTURE.md).

## Implementation sequence

1. Implement schema, migrations and domain invariants; test initial circular note/revision creation.
2. Implement authentication and note services with atomic concurrency/idempotency.
3. Add projects/Inbox, move services and responsive project/list/editor/history/trash UI.
4. Add scoped FTS and project/workspace snapshot exports.
5. Add history usage counts and validate toolbar/accessibility behavior.
6. Validate Docker deployment and backup restoration using synthetic data.
7. Review acceptance results before storing important notes.

## Deliberately absent

Nested folders, project deletion/archive, checkpoints, manual/automatic revision cleanup, tags, properties, backlinks, tasks, attachments, rich document editing, image editing, visual diffs, scheduled pruning, permanent note deletion, PWA/offline sync, AI queues, OCR, embeddings, model tooling and training tables.

Future AI logging requirements remain documented in architecture; the first AI feature must implement them before processing real user content.

## Definition of done

All acceptance scenarios have recorded verification, CI covers critical service behavior, setup and recovery instructions are reproducible, and the README accurately describes implemented behavior and limitations. A populated specification repository alone does not satisfy this milestone.
