"""Read-only HTTP surface for retained historical revision content."""
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse

from .auth import SESSION_COOKIE, authenticated_user
from .services import Notebook, ServiceError


def _error(error):
    status = {
        "authentication_required": 401,
        "not_found": 404,
        "validation_error": 400,
        "temporarily_unavailable": 503,
    }.get(error.code, 500)
    return JSONResponse({"error": error.code}, status_code=status)


def install_history_web(app, engine):
    @app.get("/api/notes/{note_id}/revisions/{revision_id}", include_in_schema=False)
    def revision_detail(request: Request, note_id: str, revision_id: str):
        raw = request.cookies.get(SESSION_COOKIE)
        user = authenticated_user(engine, raw)
        if not user:
            return _error(ServiceError("authentication_required"))
        try:
            revision = Notebook(engine, user["id"]).get_revision(
                str(UUID(note_id)), str(UUID(revision_id))
            )
            return {
                "revision_id": revision["id"],
                "note_id": revision["note_id"],
                "revision_number": revision["revision_number"],
                "title": revision["title"],
                "body_markdown": revision["body_markdown"],
                "content_format": revision["content_format"],
                "content_schema_version": revision["content_schema_version"],
                "actor_type": revision["actor_type"],
                "source_type": revision["source_type"],
                "created_at": revision["created_at"],
                "restored_from_revision_id": revision["restored_from_revision_id"],
            }
        except (ValueError, ServiceError) as error:
            if isinstance(error, ValueError):
                error = ServiceError("validation_error", field="id")
            return _error(error)
