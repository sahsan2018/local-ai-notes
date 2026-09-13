import io
import json
from pathlib import Path
from uuid import uuid4
import zipfile

import pytest
import yaml
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from local_ai_notes.cli import create_owner
from local_ai_notes.db import database_engine
from local_ai_notes.export import ExportService, build_archive, remove_temp
from local_ai_notes.main import create_app
from local_ai_notes.services import Notebook


def key():
    return str(uuid4())


@pytest.fixture
def export_db(tmp_path, monkeypatch):
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


def parse_markdown(data):
    text = data.decode("utf-8") if isinstance(data, bytes) else data
    assert text.startswith("---\n")
    front, body = text[4:].split("---\n", 1)
    return yaml.safe_load(front), body


def test_note_export_yaml_uuid_and_trash_exclusion(export_db):
    engine, owner = export_db
    book = Notebook(engine, owner)
    created = book.execute("create_note", key(), title='A: # "quoted"', body_markdown="héllo\nworld")
    client = login(TestClient(create_app(engine, cookie_secure=False)))
    response = client.get(f"/api/notes/{created['id']}/export")
    assert response.status_code == 200
    assert f'filename="{created["id"]}.md"' in response.headers["content-disposition"]
    meta, body = parse_markdown(response.content)
    assert meta["note_id"] == created["id"]
    assert meta["revision_id"] == created["current_revision_id"]
    assert meta["title"] == 'A: # "quoted"'
    assert body == "héllo\nworld"
    book.execute("trash_note", key(), note_id=created["id"], expected_version=1)
    assert client.get(f"/api/notes/{created['id']}/export").status_code == 404


def test_project_archive_flat_uuid_paths_and_empty_project(export_db):
    engine, owner = export_db
    book = Notebook(engine, owner)
    project = book.execute("create_project", key(), name="../../unsafe:name")["id"]
    first = book.execute("create_note", key(), project_id=project, title="same", body_markdown="one")
    second = book.execute("create_note", key(), project_id=project, title="same", body_markdown="two")
    client = login(TestClient(create_app(engine, cookie_secure=False)))
    response = client.get(f"/api/projects/{project}/export")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert names == {"manifest.json", f"notes/{first['id']}.md", f"notes/{second['id']}.md"}
        assert all(".." not in name and "\\" not in name for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["project"]["name"] == "../../unsafe:name"
        assert {n["note_id"] for n in manifest["notes"]} == {first["id"], second["id"]}

    empty = book.execute("create_project", key(), name="Empty")["id"]
    empty_response = client.get(f"/api/projects/{empty}/export")
    with zipfile.ZipFile(io.BytesIO(empty_response.content)) as archive:
        assert archive.namelist() == ["manifest.json"]
        assert json.loads(archive.read("manifest.json"))["notes"] == []


def test_workspace_preserves_empty_projects_inbox_and_excludes_trash(export_db):
    engine, owner = export_db
    book = Notebook(engine, owner)
    inbox = next(p for p in book.list_projects() if p["is_inbox"])
    empty = book.execute("create_project", key(), name="Empty")["id"]
    active = book.execute("create_note", key(), title="Active", body_markdown="saved")
    trashed = book.execute("create_note", key(), title="Trash", body_markdown="gone")
    book.execute("trash_note", key(), note_id=trashed["id"], expected_version=1)
    client = login(TestClient(create_app(engine, cookie_secure=False)))
    response = client.get("/api/export/workspace")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        projects = {p["project_id"]: p for p in manifest["projects"]}
        assert empty in projects
        assert projects[inbox["id"]]["is_inbox"] is True
        assert {n["note_id"] for n in manifest["notes"]} == {active["id"]}
        assert f"notes/{trashed['id']}.md" not in archive.namelist()


def test_snapshot_serialization_is_detached_from_later_mutations(export_db):
    engine, owner = export_db
    book = Notebook(engine, owner)
    note = book.execute("create_note", key(), title="Before", body_markdown="old")
    service = ExportService(engine, owner)
    snapshot = service.capture_workspace()
    book.execute("update_note", key(), note_id=note["id"], expected_version=1, title="After", body_markdown="new")
    path, _ = build_archive(snapshot)
    try:
        with zipfile.ZipFile(path) as archive:
            meta, body = parse_markdown(archive.read(f"notes/{note['id']}.md"))
            assert meta["revision_id"] == note["current_revision_id"]
            assert meta["title"] == "Before"
            assert body == "old"
    finally:
        remove_temp(path)


def test_export_requires_authentication_and_ui_marks_saved_only(export_db):
    engine, owner = export_db
    book = Notebook(engine, owner)
    note = book.execute("create_note", key(), title="N")
    anonymous = TestClient(create_app(engine, cookie_secure=False))
    assert anonymous.get(f"/api/notes/{note['id']}/export").status_code == 401
    client = login(TestClient(create_app(engine, cookie_secure=False)))
    page = client.get(f"/app?note={note['id']}").text
    assert 'id="note-export"' in page
    assert "Exports contain the last saved note content." in page
