from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config

from local_ai_notes.auth import authenticated_user, issue_session
from local_ai_notes.backup import RecoveryError, create_backup, sha256_file, verify_backup
from local_ai_notes.cli import create_owner
from local_ai_notes.db import database_engine
from local_ai_notes.restore import restore_backup
from local_ai_notes.search import rebuild_search_index
from local_ai_notes.services import Notebook


def key():
    return str(uuid4())


@pytest.fixture
def recovery_db(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    url = f"sqlite:///{source}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    engine = database_engine(url)
    owner = create_owner(engine, "owner", "synthetic password")
    yield engine, owner, source
    engine.dispose()


def populate(engine, owner):
    book = Notebook(engine, owner)
    inbox = next(p for p in book.list_projects(100) if p["is_inbox"])
    book.execute("rename_project", key(), project_id=inbox["id"], expected_version=inbox["version"], name="Renamed Inbox")
    project = book.execute("create_project", key(), name="Project A")["id"]
    empty = book.execute("create_project", key(), name="Empty Project")["id"]
    note = book.execute("create_note", key(), project_id=project, title="Unicode café", body_markdown="backup needle alpha")
    edited = book.execute("update_note", key(), note_id=note["id"], expected_version=1, title="Unicode café", body_markdown="backup needle beta")
    moved = book.execute("create_note", key(), title="Moved", body_markdown="from inbox")
    moved = book.execute("move_note", key(), note_id=moved["id"], expected_version=1, destination_project_id=project)
    trashed = book.execute("create_note", key(), project_id=project, title="Trash", body_markdown="retained")
    book.execute("update_note", key(), note_id=trashed["id"], expected_version=1, title="Trash", body_markdown="retained v2")
    book.execute("trash_note", key(), note_id=trashed["id"], expected_version=2)
    return {
        "inbox": inbox["id"], "project": project, "empty": empty,
        "note": note["id"], "revision": edited["current_revision_id"],
        "moved": moved["id"], "trashed": trashed["id"],
    }


def test_backup_verify_checksum_and_overwrite_guard(recovery_db, tmp_path):
    engine, owner, source = recovery_db
    populate(engine, owner)
    destination = tmp_path / "backup.sqlite"
    info = create_backup(destination)
    assert info["schema_version"] == "0002"
    assert info["sha256"] == sha256_file(destination)
    assert info["notes"] == 3 and info["revisions"] == 5
    with pytest.raises(RecoveryError):
        create_backup(destination)
    replaced = create_backup(destination, overwrite=True)
    assert replaced["sha256"] == sha256_file(destination)
    assert source.is_file()


def test_verify_rejects_corrupt_and_unrelated_sqlite(tmp_path):
    corrupt = tmp_path / "bad.sqlite"
    corrupt.write_text("not sqlite")
    with pytest.raises(RecoveryError):
        verify_backup(corrupt)
    unrelated = tmp_path / "other.sqlite"
    connection = sqlite3.connect(unrelated)
    connection.execute("CREATE TABLE x (id INTEGER)")
    connection.close()
    with pytest.raises(RecoveryError):
        verify_backup(unrelated)


def test_restore_separate_database_preserves_state_and_revokes_sessions(recovery_db, tmp_path):
    engine, owner, _ = recovery_db
    ids = populate(engine, owner)
    issued = issue_session(engine, "owner", "synthetic password")
    assert issued and authenticated_user(engine, issued["token"])
    backup = tmp_path / "backup.sqlite"
    create_backup(backup)

    restored = tmp_path / "restored.db"
    result = restore_backup(backup, f"sqlite:///{restored}")
    assert result["safety_backup"] is None
    restored_engine = database_engine(f"sqlite:///{restored}")
    try:
        assert authenticated_user(restored_engine, issued["token"]) is None
        assert issue_session(restored_engine, "owner", "synthetic password")
        book = Notebook(restored_engine, owner)
        projects = {p["id"]: p for p in book.list_projects(100)}
        assert projects[ids["inbox"]]["is_inbox"]
        assert projects[ids["inbox"]]["name"] == "Renamed Inbox"
        assert ids["empty"] in projects
        assert book.get_note(ids["note"])["current_revision_id"] == ids["revision"]
        assert len(book.list_revisions(ids["note"], 100)) == 2
        assert book.get_note(ids["moved"])["project_id"] == ids["project"]
        assert book.get_note(ids["trashed"])["deleted_at"] is not None
        before = [r["id"] for r in book.search_notes(ids["project"], "backup needle", 100)]
        rebuild_search_index(restored_engine)
        after = [r["id"] for r in book.search_notes(ids["project"], "backup needle", 100)]
        assert before == after == [ids["note"]]
    finally:
        restored_engine.dispose()


def test_restore_existing_target_requires_confirmation_and_creates_safety_backup(recovery_db, tmp_path):
    engine, owner, _ = recovery_db
    populate(engine, owner)
    backup = tmp_path / "backup.sqlite"
    create_backup(backup)

    target = tmp_path / "target.db"
    target_url = f"sqlite:///{target}"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", target_url)
    command.upgrade(config, "head")
    target_engine = database_engine(target_url)
    create_owner(target_engine, "oldowner", "different password")
    target_engine.dispose()

    with pytest.raises(RecoveryError):
        restore_backup(backup, target_url)
    result = restore_backup(backup, target_url, confirm_replace=True)
    assert result["safety_backup"]
    assert Path(result["safety_backup"]).exists()
    assert verify_backup(result["safety_backup"])["users"] == 1
    assert verify_backup(target)["notes"] == 3
