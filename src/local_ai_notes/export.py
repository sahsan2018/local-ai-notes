"""Portable current-state exports. SQLite remains the authoritative store."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from uuid import UUID
import zipfile

import yaml
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .services import ServiceError, identifier

EXPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ExportNoteSnapshot:
    note_id: str
    revision_id: str
    revision_number: int
    project_id: str
    project_name: str
    title: str
    body_markdown: str
    created_at: str
    updated_at: str
    revision_created_at: str
    content_format: str
    content_schema_version: int


@dataclass(frozen=True)
class ExportProjectSnapshot:
    project_id: str
    name: str
    description: str
    is_inbox: bool
    notes: tuple[ExportNoteSnapshot, ...]


@dataclass(frozen=True)
class ExportWorkspaceSnapshot:
    projects: tuple[ExportProjectSnapshot, ...]


class ExportService:
    """Trusted export capability for one authenticated actor."""

    def __init__(self, engine, actor_id):
        self.engine = engine
        self.actor = identifier(actor_id)

    def _authorize(self, connection):
        if not connection.execute(text("SELECT 1 FROM users WHERE id=:owner"), {"owner": self.actor}).first():
            raise ServiceError("authentication_required")

    @staticmethod
    def _note_from_row(row):
        return ExportNoteSnapshot(
            note_id=row["note_id"], revision_id=row["revision_id"],
            revision_number=row["revision_number"], project_id=row["project_id"],
            project_name=row["project_name"], title=row["title"],
            body_markdown=row["body_markdown"], created_at=row["note_created_at"],
            updated_at=row["note_updated_at"], revision_created_at=row["revision_created_at"],
            content_format=row["content_format"],
            content_schema_version=row["content_schema_version"],
        )

    def capture_note(self, note_id):
        note_id = identifier(note_id)
        try:
            with self.engine.connect() as connection:
                self._authorize(connection)
                result = connection.execute(text("""
                    SELECT n.id AS note_id,n.current_revision_id AS revision_id,
                           r.revision_number,n.project_id,p.name AS project_name,
                           r.title,r.body_markdown,n.created_at AS note_created_at,
                           n.updated_at AS note_updated_at,r.created_at AS revision_created_at,
                           r.content_format,r.content_schema_version
                    FROM notes n
                    JOIN projects p ON p.id=n.project_id AND p.owner_id=n.owner_id
                    JOIN note_revisions r ON r.id=n.current_revision_id
                    WHERE n.id=:note AND n.owner_id=:owner AND n.deleted_at IS NULL
                """), {"note": note_id, "owner": self.actor}).mappings().first()
                if result is None:
                    raise ServiceError("not_found")
                return self._note_from_row(result)
        except OperationalError:
            raise ServiceError("temporarily_unavailable") from None

    def capture_project(self, project_id):
        project_id = identifier(project_id)
        try:
            with self.engine.connect() as connection:
                self._authorize(connection)
                rows = list(connection.execute(text("""
                    SELECT p.id AS project_id,p.name AS project_name,p.description,p.is_inbox,
                           n.id AS note_id,n.current_revision_id AS revision_id,r.revision_number,
                           r.title,r.body_markdown,n.created_at AS note_created_at,
                           n.updated_at AS note_updated_at,r.created_at AS revision_created_at,
                           r.content_format,r.content_schema_version
                    FROM projects p
                    LEFT JOIN notes n ON n.project_id=p.id AND n.owner_id=p.owner_id
                                      AND n.deleted_at IS NULL
                    LEFT JOIN note_revisions r ON r.id=n.current_revision_id
                    WHERE p.id=:project AND p.owner_id=:owner
                    ORDER BY n.id
                """), {"project": project_id, "owner": self.actor}).mappings())
                if not rows:
                    raise ServiceError("not_found")
                first = rows[0]
                notes = tuple(self._note_from_row(row) for row in rows if row["note_id"] is not None)
                return ExportProjectSnapshot(
                    project_id=first["project_id"], name=first["project_name"],
                    description=first["description"], is_inbox=bool(first["is_inbox"]),
                    notes=notes,
                )
        except OperationalError:
            raise ServiceError("temporarily_unavailable") from None

    def capture_workspace(self):
        try:
            with self.engine.connect() as connection:
                self._authorize(connection)
                rows = list(connection.execute(text("""
                    SELECT p.id AS project_id,p.name AS project_name,p.description,p.is_inbox,
                           n.id AS note_id,n.current_revision_id AS revision_id,r.revision_number,
                           r.title,r.body_markdown,n.created_at AS note_created_at,
                           n.updated_at AS note_updated_at,r.created_at AS revision_created_at,
                           r.content_format,r.content_schema_version
                    FROM projects p
                    LEFT JOIN notes n ON n.project_id=p.id AND n.owner_id=p.owner_id
                                      AND n.deleted_at IS NULL
                    LEFT JOIN note_revisions r ON r.id=n.current_revision_id
                    WHERE p.owner_id=:owner
                    ORDER BY p.id,n.id
                """), {"owner": self.actor}).mappings())
                projects = []
                current_id = None
                current = None
                current_notes = []
                for row in rows:
                    if row["project_id"] != current_id:
                        if current is not None:
                            projects.append(ExportProjectSnapshot(
                                project_id=current["project_id"], name=current["project_name"],
                                description=current["description"], is_inbox=bool(current["is_inbox"]),
                                notes=tuple(current_notes),
                            ))
                        current_id = row["project_id"]
                        current = row
                        current_notes = []
                    if row["note_id"] is not None:
                        current_notes.append(self._note_from_row(row))
                if current is not None:
                    projects.append(ExportProjectSnapshot(
                        project_id=current["project_id"], name=current["project_name"],
                        description=current["description"], is_inbox=bool(current["is_inbox"]),
                        notes=tuple(current_notes),
                    ))
                return ExportWorkspaceSnapshot(projects=tuple(projects))
        except OperationalError:
            raise ServiceError("temporarily_unavailable") from None


def exported_at_now():
    return datetime.now(timezone.utc).isoformat()


def note_filename(note_id):
    canonical = str(UUID(note_id))
    return f"notes/{canonical}.md"


def note_frontmatter(note, exported_at):
    return {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "note_id": note.note_id,
        "revision_id": note.revision_id,
        "revision_number": note.revision_number,
        "project_id": note.project_id,
        "project_name": note.project_name,
        "title": note.title,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "revision_created_at": note.revision_created_at,
        "content_format": note.content_format,
        "content_schema_version": note.content_schema_version,
        "exported_at": exported_at,
    }


def serialize_note_markdown(note, exported_at):
    frontmatter = yaml.safe_dump(
        note_frontmatter(note, exported_at), sort_keys=False,
        allow_unicode=True, default_flow_style=False,
    )
    return f"---\n{frontmatter}---\n{note.body_markdown}".encode("utf-8")


def _note_manifest(note):
    return {
        "note_id": note.note_id,
        "revision_id": note.revision_id,
        "revision_number": note.revision_number,
        "filename": note_filename(note.note_id),
        "project_id": note.project_id,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


def _project_manifest(project):
    return {
        "project_id": project.project_id,
        "name": project.name,
        "description": project.description,
        "is_inbox": project.is_inbox,
    }


def project_manifest(snapshot, generated_at):
    return {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "export_type": "project",
        "generated_at": generated_at,
        "project": _project_manifest(snapshot),
        "notes": [_note_manifest(note) for note in snapshot.notes],
    }


def workspace_manifest(snapshot, generated_at):
    projects = list(snapshot.projects)
    notes = sorted((note for project in projects for note in project.notes), key=lambda note: note.note_id)
    return {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "export_type": "workspace",
        "generated_at": generated_at,
        "projects": [_project_manifest(project) for project in projects],
        "notes": [_note_manifest(note) for note in notes],
    }


def _safe_member(path):
    pure = Path(path)
    if pure.is_absolute() or ".." in pure.parts or "\\" in path:
        raise ServiceError("temporarily_unavailable")
    return path


def build_archive(snapshot):
    generated_at = exported_at_now()
    if isinstance(snapshot, ExportProjectSnapshot):
        manifest = project_manifest(snapshot, generated_at)
        notes = snapshot.notes
        prefix = f"local-ai-notes-project-{snapshot.project_id}-"
    elif isinstance(snapshot, ExportWorkspaceSnapshot):
        manifest = workspace_manifest(snapshot, generated_at)
        notes = tuple(sorted(
            (note for project in snapshot.projects for note in project.notes),
            key=lambda note: note.note_id,
        ))
        prefix = "local-ai-notes-workspace-"
    else:
        raise TypeError("Unsupported export snapshot")

    path = None
    try:
        handle = tempfile.NamedTemporaryFile(prefix=prefix, suffix=".zip", delete=False)
        path = handle.name
        handle.close()
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            for note in notes:
                member = _safe_member(note_filename(note.note_id))
                archive.writestr(member, serialize_note_markdown(note, generated_at))
        return path, generated_at
    except (OSError, zipfile.BadZipFile):
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
        raise ServiceError("temporarily_unavailable") from None


def remove_temp(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
