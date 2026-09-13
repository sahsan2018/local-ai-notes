from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from local_ai_notes.cli import create_owner
from local_ai_notes.db import database_engine
from local_ai_notes.main import create_app
from local_ai_notes.search import rebuild_search_index
from local_ai_notes.services import Notebook, ServiceError
from local_ai_notes.web import render_search_snippet


def key():
    return str(uuid4())


@pytest.fixture
def search_db(tmp_path, monkeypatch):
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
    response = client.post("/login", data={"username": "owner", "password": "synthetic password", "csrf": token}, follow_redirects=False)
    assert response.status_code == 303
    return client


def test_search_scope_literal_terms_and_ranking(search_db):
    engine, owner = search_db
    book = Notebook(engine, owner)
    inbox = next(p["id"] for p in book.list_projects() if p["is_inbox"])
    other = book.execute("create_project", key(), name="Other")["id"]
    title_hit = book.execute("create_note", key(), project_id=inbox, title="Raspberry Pi Backup", body_markdown="ordinary notes")
    body_hit = book.execute("create_note", key(), project_id=inbox, title="Server", body_markdown="raspberry pi backup procedure")
    outside = book.execute("create_note", key(), project_id=other, title="Raspberry Pi Backup Elsewhere")

    results = book.search_notes(inbox, "raspberry pi backup")
    assert [r["id"] for r in results] == [title_hit["id"], body_hit["id"]]
    assert outside["id"] not in [r["id"] for r in results]
    assert outside["id"] in [r["id"] for r in book.search_notes(None, "raspberry pi backup")]

    operator_note = book.execute("create_note", key(), project_id=inbox, title="OR syntax", body_markdown="hello OR secret")
    literal = book.search_notes(inbox, "hello OR secret")
    assert [r["id"] for r in literal] == [operator_note["id"]]


def test_search_tracks_current_active_content_and_rebuild(search_db):
    engine, owner = search_db
    book = Notebook(engine, owner)
    created = book.execute("create_note", key(), title="Alpha", body_markdown="firstword")
    note_id = created["id"]
    assert book.search_notes(None, "firstword")[0]["id"] == note_id

    edited = book.execute("update_note", key(), note_id=note_id, expected_version=1, title="Alpha", body_markdown="secondword")
    assert book.search_notes(None, "firstword") == []
    assert book.search_notes(None, "secondword")[0]["id"] == note_id

    book.execute("trash_note", key(), note_id=note_id, expected_version=edited["version"])
    assert book.search_notes(None, "secondword") == []
    restored = book.execute("restore_note", key(), note_id=note_id, expected_version=edited["version"] + 1)
    assert book.search_notes(None, "secondword")[0]["id"] == note_id

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM note_search"))
    assert book.search_notes(None, "secondword") == []
    assert rebuild_search_index(engine) == 1
    assert book.search_notes(None, "secondword")[0]["id"] == note_id
    assert restored["version"] == edited["version"] + 2


def test_search_failure_rolls_back_note_mutation(search_db):
    engine, owner = search_db
    book = Notebook(engine, owner)
    created = book.execute("create_note", key(), title="Stable", body_markdown="before")
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE note_search"))
    with pytest.raises(ServiceError, match="temporarily_unavailable"):
        book.execute("update_note", key(), note_id=created["id"], expected_version=1,
                     title="Changed", body_markdown="after")
    current = book.get_note(created["id"])
    assert current["version"] == 1
    assert current["title"] == "Stable"
    assert current["body_markdown"] == "before"
    assert len(book.list_revisions(created["id"])) == 1


def test_history_usage_counts_utf8_and_trash(search_db):
    engine, owner = search_db
    book = Notebook(engine, owner)
    created = book.execute("create_note", key(), title="é", body_markdown="🙂")
    book.execute("update_note", key(), note_id=created["id"], expected_version=1,
                 title="éé", body_markdown="🙂🙂")
    note_usage = book.get_history_usage(created["id"])
    expected = len("é".encode()) + len("🙂".encode()) + len("éé".encode()) + len("🙂🙂".encode())
    assert note_usage == {"revision_count": 2, "approximate_content_bytes": expected}
    book.execute("trash_note", key(), note_id=created["id"], expected_version=2)
    assert book.get_history_usage(created["id"]) == note_usage
    assert book.get_history_usage() == note_usage


def test_search_http_cursor_usage_and_safe_snippet(search_db):
    engine, owner = search_db
    book = Notebook(engine, owner)
    inbox = next(p["id"] for p in book.list_projects() if p["is_inbox"])
    for i in range(3):
        book.execute("create_note", key(), project_id=inbox, title=f"Match {i}",
                     body_markdown="needle <script>alert(1)</script>")
    client = login(TestClient(create_app(engine, cookie_secure=False)))

    page = client.get(f"/api/search?project_id={inbox}&q=needle&limit=1").json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    assert "[[LAN_HIT" not in page["items"][0]["snippet"]
    assert client.get(f"/api/search?project_id={inbox}&q=other&limit=1&cursor={page['next_cursor']}").status_code == 400

    usage = client.get(f"/api/notes/{page['items'][0]['note_id']}/history-usage")
    assert usage.status_code == 200 and usage.json()["revision_count"] == 1
    rendered = render_search_snippet('x <script>alert(1)</script> [[LAN_HIT_START]]needle[[LAN_HIT_END]]')
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "<mark>needle</mark>" in rendered


def test_search_query_limits(search_db):
    _, owner = search_db
    book = Notebook(search_db[0], owner)
    with pytest.raises(ServiceError, match="validation_error"):
        book.search_notes(None, "x " * 33)
    with pytest.raises(ServiceError, match="validation_error"):
        book.search_notes(None, "x" * 501)
