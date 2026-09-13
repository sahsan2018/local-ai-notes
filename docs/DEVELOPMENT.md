# Development

This branch implements the storage foundation, application services, authenticated browser notebook and the scoped search/history-usage work described in [stage 4](STAGE_4.md). Exports, tested backup/restore and AI remain later work; v0.0.1 is not complete.

## Local setup

Python 3.12 is the initial tested baseline. From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
mkdir -p data
export DATABASE_URL=sqlite:///./data/notes.db
export LOCAL_AI_NOTES_COOKIE_SECURE=false
alembic upgrade head
notes create-owner --username owner
uvicorn local_ai_notes.main:create_app --factory --host 127.0.0.1
```

Open `http://127.0.0.1:8000/login`. `LOCAL_AI_NOTES_COOKIE_SECURE=false` is only for explicit local HTTP development. Secure cookies are the default; leave them enabled behind HTTPS/Tailscale Serve or another trusted TLS endpoint. Environment files are examples and are not automatically loaded.

PowerShell: activate with `.venv\Scripts\Activate.ps1`, create `data` with `New-Item -ItemType Directory -Force data`, set `$env:DATABASE_URL='sqlite:///./data/notes.db'`, and set `$env:LOCAL_AI_NOTES_COOKIE_SECURE='false'` only for local HTTP development.

The administrative commands prompt twice without echoing the password. Initial passwords require 12-1024 characters and are hashed using Argon2id. Bootstrap creates one normalized owner account and Inbox atomically. Local recovery uses `notes reset-password --username owner`; a successful reset revokes every existing browser session. `notes rebuild-search` reconstructs the derived FTS index from current active revisions and does not modify canonical note/history data.

## Docker setup

```sh
docker compose build
docker compose run --rm app alembic upgrade head
docker compose run --rm app notes create-owner --username owner
docker compose up -d --wait
```

Only loopback port 8000 is published. The container runs as UID 10001 and uses a named volume at /data. Migrations are explicit and never run during a health request or automatically at server startup. Do not use `docker compose down -v` on data you want to retain.

A later Pi deployment can use an OMV bind mount owned by UID 10001 with appropriate permissions. Keep the database on a locally mounted disk, not SMB. Do not open the application port publicly. Exact host paths and Tailscale configuration stay out of source. ARM64/Pi execution still requires an on-device check before real use.

## Browser/security behavior

- Sessions are seven-day absolute sessions stored as hashes in SQLite and carried by HttpOnly, SameSite=Strict cookies.
- Browser writes require CSRF tokens and same-origin requests.
- The server resolves actor identity from the session; client actor/provenance fields are rejected.
- Markdown preview disables raw HTML, strips unsafe link schemes and does not render remote images.
- Search accepts literal AND-combined terms only, scopes before returning results and safely escapes browser snippets.
- The login throttle is intentionally in-process for the single-process initial deployment; it is not a substitute for a distributed limiter if the deployment topology changes.

## Health and verification

- `/health/live` reports that the process responds.
- `/health/ready` returns 200 only when the database is reachable at schema 0002; otherwise 503 without database details.
- Run `pytest -q` for foundation, services, authentication, browser conflict, search/index lifecycle, cursor/scope, usage and sanitization tests.
- CI also builds and starts the Docker image after migrating an empty named volume.

Readiness targets migration 0002 but does not audit every FTS row. Search is rebuildable derived state. Readiness does not promise sufficient disk space, write access, owner setup or backup health. Destructive downgrades remain disabled; a tested end-user backup/restore workflow is still pending.

## Dependency and release limits

Dependencies have bounded version ranges, not a production lockfile. CI resolves them on each run. Add a reproducible release lock and perform dependency/security review before packaging a stable release.
