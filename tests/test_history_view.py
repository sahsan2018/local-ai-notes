from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from local_ai_notes.cli import create_owner
from local_ai_notes.db import database_engine
from local_ai_notes.main import create_app
from local_ai_notes.services import Notebook


def key():
    return str(uuid4())


@pytest.fixture
def history_db(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'notes.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    engine = database_engine(url)
    owner = create_owner(engine, "owner", "synthetic password")
    yield engine, owner
    engine.dispose()


def login(client):
    assert client.get("/login").status_code == 200
    token = client.cookies.get("lan_login_csrf")
    response = client.post(
        "/login",
        data={"username": "owner", "password": "synthetic password", "csrf": token},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_revision_detail_requires_auth_and_returns_historical_content(history_db):
    engine, owner = history_db
    book = Notebook(engine, owner)
    created = book.execute("create_note", key(), title="First title", body_markdown="first body")
    historical_id = created["current_revision_id"]
    updated = book.execute(
        "update_note", key(), note_id=created["id"], expected_version=1,
        title="Second title", body_markdown="second body",
    )

    client = TestClient(create_app(engine, cookie_secure=False))
    path = f"/api/notes/{created['id']}/revisions/{historical_id}"
    assert client.get(path).status_code == 401

    login(client)
    response = client.get(path)
    assert response.status_code == 200
    detail = response.json()
    assert detail["note_id"] == created["id"]
    assert detail["revision_id"] == historical_id
    assert detail["revision_number"] == 1
    assert detail["title"] == "First title"
    assert detail["body_markdown"] == "first body"
    assert detail["restored_from_revision_id"] is None

    current = client.get(f"/api/notes/{created['id']}/revisions/{updated['current_revision_id']}")
    assert current.status_code == 200
    assert current.json()["revision_number"] == 2
    assert current.json()["title"] == "Second title"


def test_revision_detail_rejects_revision_from_another_note(history_db):
    engine, owner = history_db
    book = Notebook(engine, owner)
    first = book.execute("create_note", key(), title="One", body_markdown="alpha")
    second = book.execute("create_note", key(), title="Two", body_markdown="beta")
    client = TestClient(create_app(engine, cookie_secure=False))
    login(client)

    response = client.get(
        f"/api/notes/{first['id']}/revisions/{second['current_revision_id']}"
    )
    assert response.status_code == 404
