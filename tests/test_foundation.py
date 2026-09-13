from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from local_ai_notes.cli import create_owner
from local_ai_notes.db import database_engine
from local_ai_notes.main import create_app


@pytest.fixture
def db(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'notes.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    engine = database_engine(url)
    yield engine
    engine.dispose()


def test_bootstrap_and_reopen(db):
    owner = create_owner(db, "  Owner  ", "a synthetic password")
    with db.connect() as c:
        row = c.execute(text("SELECT * FROM users")).mappings().one()
        assert row['username'] == 'owner'
        assert PasswordHasher().verify(row['password_hash'], 'a synthetic password')
        assert c.execute(text("SELECT owner_id FROM projects WHERE is_inbox=1")).scalar() == owner
        assert c.execute(text("SELECT count(*) FROM audit_events")).scalar() == 1
    db.dispose()
    with db.connect() as c:
        assert c.execute(text("SELECT count(*) FROM users")).scalar() == 1
    with pytest.raises(ValueError, match="already exists"):
        create_owner(db, "another", "another synthetic password")


def test_bootstrap_rolls_back(db):
    with db.begin() as c:
        c.exec_driver_sql("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_events BEGIN SELECT RAISE(ABORT, 'injected'); END")
    with pytest.raises(IntegrityError):
        create_owner(db, "owner", "a synthetic password")
    with db.connect() as c:
        for table in ('users', 'projects', 'audit_events'):
            assert c.exec_driver_sql(f"SELECT count(*) FROM {table}").scalar() == 0


def seed_note(db, note='n1', revision='r1'):
    with db.begin() as c:
        owner, project = c.exec_driver_sql("SELECT owner_id,id FROM projects").one()
        c.exec_driver_sql("INSERT INTO notes VALUES (?,?,?,?,1,2,'now','now',NULL)", (note, owner, project, revision))
        c.exec_driver_sql("INSERT INTO note_revisions VALUES (?,?,1,'Title','markdown',1,'Body','user',?,'manual','req','now',NULL)", (revision, note, owner))


def test_deferred_revision_and_constraints(db):
    create_owner(db, 'owner', 'a synthetic password')
    seed_note(db)
    seed_note(db, 'n2', 'r2')
    with pytest.raises(IntegrityError):
        with db.begin() as c:
            c.exec_driver_sql("UPDATE notes SET current_revision_id='r2' WHERE id='n1'")
    with pytest.raises(IntegrityError):
        with db.begin() as c:
            c.exec_driver_sql("UPDATE note_revisions SET body_markdown='changed' WHERE id='r1'")
    with pytest.raises(IntegrityError):
        with db.begin() as c:
            c.exec_driver_sql("DELETE FROM note_revisions WHERE id='r1'")
    with pytest.raises(IntegrityError):
        with db.begin() as c:
            c.exec_driver_sql("UPDATE notes SET project_id='missing' WHERE id='n1'")
    with db.connect() as c:
        assert c.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert c.exec_driver_sql("SELECT body_markdown FROM note_revisions WHERE id='r1'").scalar() == 'Body'


def test_missing_initial_revision_rejected(db):
    create_owner(db, 'owner', 'a synthetic password')
    with pytest.raises(IntegrityError):
        with db.begin() as c:
            owner, project = c.exec_driver_sql("SELECT owner_id,id FROM projects").one()
            c.exec_driver_sql("INSERT INTO notes VALUES ('n',?,?,'missing',1,2,'now','now',NULL)", (owner, project))
    with db.connect() as c:
        assert c.exec_driver_sql("SELECT count(*) FROM notes").scalar() == 0


def test_single_owner_and_inbox(db):
    create_owner(db, 'owner', 'a synthetic password')
    with pytest.raises(IntegrityError):
        with db.begin() as c:
            c.exec_driver_sql("INSERT INTO users VALUES ('other','other','hash','now')")
    with pytest.raises(IntegrityError):
        with db.begin() as c:
            owner = c.exec_driver_sql("SELECT id FROM users").scalar()
            c.exec_driver_sql("INSERT INTO projects VALUES ('duplicate',?,'Inbox','',1,1,'now','now')", (owner,))


def test_health(db, tmp_path):
    with TestClient(create_app(db)) as client:
        assert client.get('/health/live').status_code == 200
        assert client.get('/health/ready').status_code == 200
        assert client.get('/notes').status_code == 404
    with TestClient(create_app(database_engine(f"sqlite:///{tmp_path / 'empty.db'}"))) as client:
        assert client.get('/health/live').status_code == 200
        response = client.get('/health/ready')
        assert response.status_code == 503
        assert response.json() == {'status': 'not_ready'}
