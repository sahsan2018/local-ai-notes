from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from local_ai_notes.auth import reset_password
from local_ai_notes.cli import create_owner
from local_ai_notes.db import database_engine
from local_ai_notes.main import create_app
from local_ai_notes.services import Notebook
from local_ai_notes.web import render_markdown


def key():
    return str(uuid4())


@pytest.fixture
def web_db(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'notes.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    engine = database_engine(url)
    owner = create_owner(engine, "owner", "synthetic password")
    yield engine, owner
    engine.dispose()


def login(client, password="synthetic password"):
    assert client.get("/login").status_code == 200
    token = client.cookies.get("lan_login_csrf")
    response = client.post("/login", data={"username": "owner", "password": password, "csrf": token}, follow_redirects=False)
    assert response.status_code == 303
    return client


def csrf(client):
    html = client.get("/app").text
    marker = 'name="csrf-token" content="'
    return html.split(marker, 1)[1].split('"', 1)[0]


def test_session_csrf_expiry_logout_and_recovery(web_db):
    engine, _ = web_db
    client = login(TestClient(create_app(engine, cookie_secure=False)))
    assert client.get("/app").status_code == 200
    assert client.post("/projects", data={"name": "X", "idempotency_key": key()}).status_code == 400
    assert client.post("/logout", data={"csrf": csrf(client)}, follow_redirects=False).status_code == 303
    assert client.get("/app", follow_redirects=False).status_code == 303

    client = login(TestClient(create_app(engine, cookie_secure=False)))
    with engine.begin() as connection:
        connection.execute(text("UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00'"))
    assert client.get("/app", follow_redirects=False).status_code == 303

    client = login(TestClient(create_app(engine, cookie_secure=False)))
    reset_password(engine, "owner", "new synthetic password")
    assert client.get("/app", follow_redirects=False).status_code == 303
    login(TestClient(create_app(engine, cookie_secure=False)), "new synthetic password")


def test_browser_conflict_retry_and_spoof_rejected(web_db):
    engine, owner = web_db
    book = Notebook(engine, owner)
    note_id = book.execute("create_note", key(), title="Start")["id"]
    first = login(TestClient(create_app(engine, cookie_secure=False)))
    second = login(TestClient(create_app(engine, cookie_secure=False)))
    payload_one = {"csrf": csrf(first), "idempotency_key": key(), "expected_version": "1", "title": "One", "body_markdown": "a"}
    payload_two = {"csrf": csrf(second), "idempotency_key": key(), "expected_version": "1", "title": "Two", "body_markdown": "b"}

    saved = first.post(f"/notes/{note_id}/save", data=payload_one)
    assert saved.status_code == 200 and saved.json()["version"] == 2
    retried = first.post(f"/notes/{note_id}/save", data=payload_one)
    assert retried.status_code == 200 and retried.json()["version"] == 2
    conflict = second.post(f"/notes/{note_id}/save", data=payload_two)
    assert conflict.status_code == 409 and conflict.json()["current"]["title"] == "One"
    assert second.post(f"/notes/{note_id}/save", data={**payload_two, "actor_id": owner}).status_code == 400


def test_scope_bound_cursor_and_direct_selection(web_db):
    engine, owner = web_db
    book = Notebook(engine, owner)
    inbox = next(project["id"] for project in book.list_projects() if project["is_inbox"])
    other = book.execute("create_project", key(), name="Other")["id"]
    note_id = book.execute("create_note", key(), project_id=other)["id"]
    book.execute("create_note", key(), project_id=other, title="Second")
    client = login(TestClient(create_app(engine, cookie_secure=False)))

    assert client.get(f"/app?project={inbox}&note={note_id}").status_code == 404
    page = client.get(f"/api/notes?project_id={other}&limit=1").json()
    assert page["items"] and page["next_cursor"]
    assert client.get(f"/api/notes?project_id={inbox}&limit=1&cursor={page['next_cursor']}").status_code == 400


def test_recent_order_request_identity_and_revision_order(web_db):
    engine, owner = web_db
    book = Notebook(engine, owner)
    first = book.execute("create_note", key(), title="A")
    book.execute("create_note", key(), title="B")
    request_id = key()
    edited = book.execute("update_note", key(), request_id=request_id, note_id=first["id"], expected_version=1, title="A2", body_markdown="")
    assert book.list_notes(None)[0]["id"] == first["id"]
    assert [row["revision_number"] for row in book.list_revisions(first["id"])] == [2, 1]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT request_id FROM note_revisions WHERE id=:id"), {"id": edited["current_revision_id"]}).scalar() == request_id


def test_markdown_preview_sanitizes_unsafe_content():
    html = render_markdown('[x](javascript:alert(1)) <script>alert(1)</script> ![remote](https://example.com/x.png)')
    assert "<script" not in html
    assert 'href="javascript:' not in html
    assert "<img" not in html
