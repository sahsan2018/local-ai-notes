import base64
import hmac
import json
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs
from uuid import UUID, uuid4

import bleach
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

from .auth import LOGIN_CSRF_COOKIE, SESSION_COOKIE, authenticated_user, issue_session, revoke_session
from .services import Notebook, ServiceError

ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))
TEMPLATES.env.globals["new_key"] = lambda: str(uuid4())
MARKDOWN = MarkdownIt("commonmark", {"html": False, "linkify": True})
ALLOWED_TAGS = ["p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "em", "ul", "ol", "li", "blockquote", "pre", "code", "a", "hr"]


class LoginLimiter:
    def __init__(self, attempts=5, window=300):
        self.attempts, self.window = attempts, window
        self.lock, self.events = threading.Lock(), {}

    def allowed(self, key):
        now = time.monotonic()
        with self.lock:
            recent = [t for t in self.events.get(key, []) if now - t < self.window]
            self.events[key] = recent
            return len(recent) < self.attempts

    def fail(self, key):
        with self.lock:
            self.events.setdefault(key, []).append(time.monotonic())

    def clear(self, key):
        with self.lock:
            self.events.pop(key, None)


def render_markdown(source):
    rendered = MARKDOWN.render(source)
    return bleach.clean(rendered, tags=ALLOWED_TAGS, attributes={"a": ["href", "title"]},
                        protocols=["http", "https", "mailto"], strip=True)


def csrf_for_session(raw):
    return hmac.new(raw.encode(), b"local-ai-notes-csrf-v1", "sha256").hexdigest()


def _b64(data):
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")


def _unb64(value):
    try:
        padded = value + "=" * (-len(value) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded).decode())
        if not isinstance(data, dict):
            raise ValueError
        return data
    except Exception:
        raise ServiceError("validation_error", field="cursor") from None


def make_cursor(kind, scope, trashed, item):
    if kind == "revisions":
        position = item["revision_number"]
    else:
        position = [item["updated_at"], item["id"]]
    return _b64({"v": 1, "kind": kind, "scope": scope, "trashed": bool(trashed), "position": position})


def parse_cursor(value, kind, scope, trashed):
    if not value:
        return None
    data = _unb64(value)
    if data.get("v") != 1 or data.get("kind") != kind or data.get("scope") != scope or bool(data.get("trashed")) != bool(trashed):
        raise ServiceError("validation_error", field="cursor")
    return data.get("position")


def _same_origin(request):
    origin = request.headers.get("origin")
    if not origin:
        return True
    return origin.rstrip("/") == str(request.base_url).rstrip("/")


async def _form(request, allowed, required=()):
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/x-www-form-urlencoded":
        raise ServiceError("validation_error", field="content_type")
    body = (await request.body()).decode("utf-8")
    parsed = {k: v[-1] for k, v in parse_qs(body, keep_blank_values=True).items()}
    if set(parsed) - set(allowed) or not set(required) <= set(parsed):
        raise ServiceError("validation_error", field="payload")
    return parsed


def _status(error):
    return {
        "authentication_required": 401, "not_found": 404, "validation_error": 400,
        "payload_too_large": 413, "version_conflict": 409, "invalid_state": 409,
        "idempotency_conflict": 409, "temporarily_unavailable": 503,
    }.get(error.code, 500)


def _json_error(error):
    body = {"error": error.code}
    if error.code == "version_conflict":
        body.update(error.details)
    return JSONResponse(body, status_code=_status(error))


def install_web(app, engine, cookie_secure=True):
    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
    limiter = LoginLimiter()

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        return response

    def session(request):
        raw = request.cookies.get(SESSION_COOKIE)
        user = authenticated_user(engine, raw)
        return raw, user

    def require(request):
        raw, user = session(request)
        if not user:
            raise ServiceError("authentication_required")
        return raw, user, Notebook(engine, user["id"])

    def check_csrf(request, raw, supplied):
        if not _same_origin(request) or not supplied or not hmac.compare_digest(csrf_for_session(raw), supplied):
            raise ServiceError("validation_error", field="csrf")

    @app.get("/", include_in_schema=False)
    def root(request: Request):
        return RedirectResponse("/app" if session(request)[1] else "/login", status_code=303)

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login_page(request: Request):
        if session(request)[1]:
            return RedirectResponse("/app", status_code=303)
        token = secrets.token_urlsafe(24)
        response = TEMPLATES.TemplateResponse(request, "login.html", {"csrf": token, "error": None})
        response.set_cookie(LOGIN_CSRF_COOKIE, token, httponly=True, secure=cookie_secure, samesite="strict", max_age=600)
        return response

    @app.post("/login", include_in_schema=False)
    async def login(request: Request):
        try:
            values = await _form(request, {"username", "password", "csrf"}, {"username", "password", "csrf"})
        except ServiceError as error:
            return _json_error(error)
        cookie = request.cookies.get(LOGIN_CSRF_COOKIE, "")
        if not _same_origin(request) or not cookie or not hmac.compare_digest(cookie, values["csrf"]):
            return JSONResponse({"error": "invalid_request"}, status_code=403)
        source = request.client.host if request.client else "unknown"
        key = f"{source}:{values['username'].strip().casefold()}"
        if not limiter.allowed(key):
            return JSONResponse({"error": "invalid_credentials"}, status_code=429)
        issued = issue_session(engine, values["username"], values["password"])
        if not issued:
            limiter.fail(key)
            return TEMPLATES.TemplateResponse(request, "login.html", {"csrf": values["csrf"], "error": "Invalid username or password."}, status_code=401)
        limiter.clear(key)
        response = RedirectResponse("/app", status_code=303)
        response.set_cookie(SESSION_COOKIE, issued["token"], httponly=True, secure=cookie_secure, samesite="strict", max_age=7 * 24 * 3600)
        response.delete_cookie(LOGIN_CSRF_COOKIE)
        return response

    @app.post("/logout", include_in_schema=False)
    async def logout(request: Request):
        raw, user = session(request)
        if not user:
            return RedirectResponse("/login", status_code=303)
        try:
            values = await _form(request, {"csrf"}, {"csrf"})
            check_csrf(request, raw, values["csrf"])
        except ServiceError as error:
            return _json_error(error)
        revoke_session(engine, raw)
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(SESSION_COOKIE)
        return response

    def list_page(book, kind, scope, trashed, limit, cursor):
        after = parse_cursor(cursor, kind, scope, trashed)
        wanted = min(limit, 100)
        fetch_limit = min(wanted + 1, 100)
        if kind == "projects":
            rows = book.list_projects(fetch_limit, after)
        elif kind == "notes":
            rows = book.list_notes(scope, trashed, fetch_limit, after)
        else:
            rows = book.list_revisions(scope, fetch_limit, after)
        more = len(rows) > wanted
        rows = rows[:wanted]
        next_cursor = make_cursor(kind, scope, trashed, rows[-1]) if more and rows else None
        return rows, next_cursor

    @app.get("/api/projects")
    def api_projects(request: Request, limit: int = 25, cursor: str = ""):
        try:
            _, _, book = require(request)
            if not 1 <= limit <= 100:
                raise ServiceError("validation_error", field="limit")
            rows, nxt = list_page(book, "projects", None, False, limit, cursor)
            return {"items": [{k: v for k, v in r.items() if k != "id"} | {"project_id": r["id"]} for r in rows], "next_cursor": nxt}
        except ServiceError as error:
            return _json_error(error)

    @app.get("/api/notes")
    def api_notes(request: Request, project_id: str, trashed: bool = False, limit: int = 25, cursor: str = ""):
        try:
            _, _, book = require(request)
            scope = None if project_id == "all" else str(UUID(project_id))
            if not 1 <= limit <= 100:
                raise ServiceError("validation_error", field="limit")
            rows, nxt = list_page(book, "notes", scope, trashed, limit, cursor)
            return {"items": [{k: v for k, v in r.items() if k != "id"} | {"note_id": r["id"]} for r in rows], "next_cursor": nxt}
        except (ValueError, ServiceError) as error:
            return _json_error(error if isinstance(error, ServiceError) else ServiceError("validation_error", field="project_id"))

    @app.get("/api/notes/{note_id}/revisions")
    def api_revisions(request: Request, note_id: str, limit: int = 25, cursor: str = ""):
        try:
            _, _, book = require(request)
            note_id = str(UUID(note_id))
            rows, nxt = list_page(book, "revisions", note_id, False, limit, cursor)
            return {"items": [{k: v for k, v in r.items() if k != "id"} | {"revision_id": r["id"]} for r in rows], "next_cursor": nxt}
        except (ValueError, ServiceError) as error:
            return _json_error(error if isinstance(error, ServiceError) else ServiceError("validation_error", field="note_id"))

    @app.get("/app", response_class=HTMLResponse, include_in_schema=False)
    def notebook_page(request: Request, project: str = "", note: str = "", trash: bool = False):
        try:
            raw, user, book = require(request)
            projects = book.list_projects(100)
            scope = None if project == "all" else (project or (next((p["id"] for p in projects if p["is_inbox"]), projects[0]["id"] if projects else None)))
            if scope is not None:
                scope = str(UUID(scope))
            notes = book.list_notes(scope, trash, 100)
            selected = None
            revisions = []
            if note:
                selected = book.get_note(note)
                if (scope is not None and selected["project_id"] != scope) or bool(selected["deleted_at"]) != bool(trash):
                    raise ServiceError("not_found")
                revisions = book.list_revisions(selected["id"], 100)
            return TEMPLATES.TemplateResponse(request, "app.html", {
                "user": user, "projects": projects, "scope": scope, "all_projects": scope is None,
                "trash": trash, "notes": notes, "selected": selected, "revisions": revisions,
                "csrf": csrf_for_session(raw),
            })
        except ValueError:
            return HTMLResponse("Not found", status_code=404)
        except ServiceError as error:
            if error.code == "authentication_required":
                return RedirectResponse("/login", status_code=303)
            return HTMLResponse("Not found" if error.code == "not_found" else "Request failed", status_code=_status(error))

    async def mutate(request, operation, allowed, required, transform=None):
        book = None
        try:
            raw, _, book = require(request)
            values = await _form(request, set(allowed) | {"csrf", "idempotency_key"}, set(required) | {"csrf", "idempotency_key"})
            check_csrf(request, raw, values.pop("csrf"))
            key = values.pop("idempotency_key")
            if transform:
                values = transform(values)
            result = book.execute(operation, key, request_id=str(uuid4()), **values)
            return result, book
        except (ValueError, ServiceError) as error:
            if isinstance(error, ValueError):
                error = ServiceError("validation_error", field="payload")
            return error, book

    @app.post("/projects", include_in_schema=False)
    async def create_project(request: Request):
        result, _ = await mutate(request, "create_project", {"name", "description"}, {"name"})
        if isinstance(result, ServiceError):
            return _json_error(result)
        return RedirectResponse(f"/app?project={result['id']}", status_code=303)

    @app.post("/projects/{project_id}/rename", include_in_schema=False)
    async def rename_project(request: Request, project_id: str):
        result, _ = await mutate(request, "rename_project", {"name", "expected_version"}, {"name", "expected_version"},
            lambda v: {**v, "project_id": project_id, "expected_version": int(v["expected_version"])})
        if isinstance(result, ServiceError):
            return _json_error(result)
        return RedirectResponse(f"/app?project={project_id}", status_code=303)

    @app.get("/notes", include_in_schema=False)
    def notes_get_not_found():
        return HTMLResponse("Not found", status_code=404)

    @app.post("/notes", include_in_schema=False)
    async def create_note(request: Request):
        result, _ = await mutate(request, "create_note", {"project_id"}, set())
        if isinstance(result, ServiceError):
            return _json_error(result)
        return RedirectResponse(f"/app?project={result['project_id']}&note={result['id']}", status_code=303)

    @app.post("/notes/{note_id}/save", include_in_schema=False)
    async def save_note(request: Request, note_id: str):
        def transform(v):
            return {"note_id": note_id, "expected_version": int(v["expected_version"]), "title": v["title"], "body_markdown": v["body_markdown"]}
        result, book = await mutate(request, "update_note", {"expected_version", "title", "body_markdown"}, {"expected_version", "title", "body_markdown"}, transform)
        if isinstance(result, ServiceError):
            if result.code == "version_conflict" and book:
                current = book.get_note(note_id)
                return JSONResponse({"error": "version_conflict", "current": {
                    "version": current["version"], "title": current["title"], "body_markdown": current["body_markdown"],
                    "revision_id": current["current_revision_id"]}}, status_code=409)
            return _json_error(result)
        return {"ok": True, "note_id": result["id"], "version": result["version"], "revision_id": result["current_revision_id"], "changed": result["changed"], "updated_at": result["updated_at"]}

    @app.post("/notes/{note_id}/move", include_in_schema=False)
    async def move_note(request: Request, note_id: str):
        result, _ = await mutate(request, "move_note", {"expected_version", "destination_project_id"}, {"expected_version", "destination_project_id"},
            lambda v: {"note_id": note_id, "expected_version": int(v["expected_version"]), "destination_project_id": v["destination_project_id"]})
        if isinstance(result, ServiceError):
            return _json_error(result)
        return RedirectResponse(f"/app?project={result['project_id']}&note={result['id']}", status_code=303)

    @app.post("/notes/{note_id}/trash", include_in_schema=False)
    async def trash_note(request: Request, note_id: str):
        result, _ = await mutate(request, "trash_note", {"expected_version"}, {"expected_version"}, lambda v: {"note_id": note_id, "expected_version": int(v["expected_version"])})
        if isinstance(result, ServiceError):
            return _json_error(result)
        return RedirectResponse(f"/app?project={result['project_id']}", status_code=303)

    @app.post("/notes/{note_id}/restore", include_in_schema=False)
    async def restore_note(request: Request, note_id: str):
        result, _ = await mutate(request, "restore_note", {"expected_version"}, {"expected_version"}, lambda v: {"note_id": note_id, "expected_version": int(v["expected_version"])})
        if isinstance(result, ServiceError):
            return _json_error(result)
        return RedirectResponse(f"/app?project={result['project_id']}&note={result['id']}", status_code=303)

    @app.post("/notes/{note_id}/revisions/{revision_id}/restore", include_in_schema=False)
    async def restore_revision(request: Request, note_id: str, revision_id: str):
        result, _ = await mutate(request, "restore_revision", {"expected_version"}, {"expected_version"}, lambda v: {"note_id": note_id, "revision_id": revision_id, "expected_version": int(v["expected_version"])})
        if isinstance(result, ServiceError):
            return _json_error(result)
        return RedirectResponse(f"/app?project={result['project_id']}&note={result['id']}", status_code=303)

    @app.post("/preview", include_in_schema=False)
    async def preview(request: Request):
        try:
            raw, _, _ = require(request)
            check_csrf(request, raw, request.headers.get("x-csrf-token", ""))
            data = await request.json()
            if set(data) != {"body_markdown"} or not isinstance(data["body_markdown"], str) or len(data["body_markdown"].encode()) > 1048576:
                raise ServiceError("validation_error", field="body_markdown")
            return HTMLResponse(render_markdown(data["body_markdown"]))
        except ServiceError as error:
            return _json_error(error)
