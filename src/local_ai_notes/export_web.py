"""Authenticated file transport for portable exports."""
from datetime import datetime
from functools import partial
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.background import BackgroundTask

from .auth import SESSION_COOKIE, authenticated_user
from .export import ExportService, build_archive, exported_at_now, remove_temp, serialize_note_markdown
from .services import ServiceError


def _status(error):
    return {
        "authentication_required": 401,
        "not_found": 404,
        "validation_error": 400,
        "temporarily_unavailable": 503,
    }.get(error.code, 500)


def _error(error):
    return JSONResponse({"error": error.code}, status_code=_status(error))


def _service(request, engine):
    raw = request.cookies.get(SESSION_COOKIE)
    user = authenticated_user(engine, raw)
    if not user:
        raise ServiceError("authentication_required")
    return ExportService(engine, user["id"])


def _workspace_filename(generated_at):
    stamp = datetime.fromisoformat(generated_at).strftime("%Y%m%dT%H%M%SZ")
    return f"local-ai-notes-workspace-{stamp}.zip"


def install_export_web(app, engine):
    @app.get("/api/notes/{note_id}/export", include_in_schema=False)
    def export_note(request: Request, note_id: str):
        try:
            snapshot = _service(request, engine).capture_note(note_id)
            exported_at = exported_at_now()
            body = serialize_note_markdown(snapshot, exported_at)
            return Response(
                body, media_type="text/markdown; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{snapshot.note_id}.md"'},
            )
        except ServiceError as error:
            return _error(error)

    @app.get("/api/projects/{project_id}/export", include_in_schema=False)
    def export_project(request: Request, project_id: str):
        path = None
        try:
            snapshot = _service(request, engine).capture_project(project_id)
            path, _ = build_archive(snapshot)
            return FileResponse(
                path, media_type="application/zip",
                filename=f"local-ai-notes-project-{snapshot.project_id}.zip",
                background=BackgroundTask(partial(remove_temp, path)),
            )
        except ServiceError as error:
            if path:
                remove_temp(path)
            return _error(error)

    @app.get("/api/export/workspace", include_in_schema=False)
    def export_workspace(request: Request):
        path = None
        try:
            snapshot = _service(request, engine).capture_workspace()
            path, generated_at = build_archive(snapshot)
            return FileResponse(
                path, media_type="application/zip", filename=_workspace_filename(generated_at),
                background=BackgroundTask(partial(remove_temp, path)),
            )
        except ServiceError as error:
            if path:
                remove_temp(path)
            return _error(error)
