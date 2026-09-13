"""Consistent SQLite backup creation and verification."""
import hashlib
import os
from pathlib import Path
import sqlite3

from sqlalchemy.engine import make_url

EXPECTED_TABLES = {
    "alembic_version", "users", "sessions", "projects", "notes",
    "note_revisions", "audit_events", "mutation_receipts", "note_search",
}


class RecoveryError(ValueError):
    pass


def database_path(url=None):
    url = url or os.environ.get("DATABASE_URL", "sqlite:///./data/notes.db")
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite" or not parsed.database or parsed.database == ":memory:":
        raise RecoveryError("Backup tooling requires a file-backed SQLite DATABASE_URL")
    return Path(parsed.database).expanduser().resolve()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_backup(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise RecoveryError("Backup file does not exist")
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            if [row[0] for row in connection.execute("PRAGMA integrity_check")] != ["ok"]:
                raise RecoveryError("SQLite integrity check failed")
            if list(connection.execute("PRAGMA foreign_key_check")):
                raise RecoveryError("SQLite foreign key check failed")
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
            )}
            if not EXPECTED_TABLES <= tables:
                raise RecoveryError("File is not a complete Local AI Notes database")
            version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            if not version or not version[0]:
                raise RecoveryError("Backup has no Alembic schema version")
            if connection.execute("""
                SELECT count(*) FROM notes n
                LEFT JOIN note_revisions r
                  ON r.id=n.current_revision_id AND r.note_id=n.id
                WHERE r.id IS NULL
            """).fetchone()[0]:
                raise RecoveryError("Backup contains invalid current revision pointers")
            if connection.execute("""
                SELECT count(*) FROM notes n
                LEFT JOIN projects p ON p.id=n.project_id AND p.owner_id=n.owner_id
                WHERE p.id IS NULL
            """).fetchone()[0]:
                raise RecoveryError("Backup contains invalid project ownership")
            if connection.execute("""
                SELECT count(*) FROM (
                    SELECT u.id, sum(CASE WHEN p.is_inbox=1 THEN 1 ELSE 0 END) AS inboxes
                    FROM users u LEFT JOIN projects p ON p.owner_id=u.id
                    GROUP BY u.id HAVING inboxes != 1
                )
            """).fetchone()[0]:
                raise RecoveryError("Backup contains an invalid Inbox identity")
            counts = {
                table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("users", "projects", "notes", "note_revisions")
            }
        finally:
            connection.close()
    except RecoveryError:
        raise
    except (sqlite3.DatabaseError, OSError) as error:
        raise RecoveryError("Backup could not be validated as SQLite") from error
    return {
        "path": str(path), "schema_version": version[0], "sha256": sha256_file(path),
        "users": counts["users"], "projects": counts["projects"],
        "notes": counts["notes"], "revisions": counts["note_revisions"],
    }


def create_backup(destination, database_url=None, overwrite=False):
    source = database_path(database_url)
    destination = Path(destination).expanduser().resolve()
    if not source.is_file():
        raise RecoveryError("Source database does not exist")
    if destination == source:
        raise RecoveryError("Backup destination must differ from the live database")
    if destination.exists() and not overwrite:
        raise RecoveryError("Backup destination already exists; use --overwrite to replace it")
    if not destination.parent.is_dir():
        raise RecoveryError("Backup destination directory does not exist")
    try:
        source_connection = sqlite3.connect(source, timeout=5)
        destination_connection = sqlite3.connect(destination)
        try:
            source_connection.backup(destination_connection)
            destination_connection.commit()
        finally:
            destination_connection.close()
            source_connection.close()
        return verify_backup(destination)
    except RecoveryError:
        raise
    except (sqlite3.DatabaseError, OSError) as error:
        raise RecoveryError("Backup could not be created") from error
