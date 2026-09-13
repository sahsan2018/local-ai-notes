# Stage 5: portable exports

This draft builds on Stage 4 search and history visibility. It adds authenticated portable exports of committed active content. Exports are current-state portability artifacts, not disaster-recovery backups.

## Implemented

- Active notes export as UTF-8 Markdown named by note UUID.
- Markdown uses YAML frontmatter serialized by PyYAML with export schema version, note/revision identity, project identity/name, timestamps and content format/version.
- Project exports are ZIP archives containing `manifest.json` plus flat `notes/<uuid>.md` members.
- Workspace exports use the same flat layout and preserve every owned project, including empty projects and the stable Inbox identity.
- Project/workspace snapshot capture finishes before ZIP serialization and HTTP transfer. Serialization never re-reads live database state.
- ZIP member names are code-generated from canonical UUIDs; note/project titles never become archive paths.
- Project/workspace ZIPs use secure temporary files and are deleted after the response completes.
- The browser exposes note, selected-project and All Projects export controls. Note export is disabled while the open editor has unsaved changes.
- Trashed notes and historical revisions are excluded. Export routes require an authenticated session and perform owner-scoped reads.

## Export format v1

Single-note files are named `<note-uuid>.md`. Archive note members are named `notes/<note-uuid>.md`.

The YAML frontmatter includes `export_schema_version`, `note_id`, `revision_id`, `revision_number`, `project_id`, `project_name`, `title`, note/revision timestamps, `content_format`, `content_schema_version` and `exported_at`. The Markdown body follows the closing frontmatter delimiter unchanged.

Project and workspace manifests include `export_schema_version`, `export_type`, `generated_at`, project metadata and note entries containing note/revision identity, membership, timestamps and archive filename. Workspace manifests preserve empty projects.

## Boundaries and limitations

Exports contain committed active content only. They do not include trash, full history, sessions, credentials, mutation receipts, audit logs or FTS state. They are generated on demand and are not retained in a server export directory.

There is no import flow, scheduled export, historical-revision export, trash export, attachment export or cloud synchronization in this stage. Stage 6 will define and test complete SQLite backup/restore separately.
