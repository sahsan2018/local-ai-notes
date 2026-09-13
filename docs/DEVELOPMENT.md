# Development

This branch implements the storage foundation, trusted services, authenticated browser notebook, scoped search/history usage, portable exports, verified SQLite backup/recovery, and v0.0.1 release-hardening work. AI remains later work; physical Pi/ARM64, OMV, phone/desktop keyboard and Tailscale acceptance must still be recorded before v0.0.1 is complete. See [v0.0.1 acceptance](V0_0_1_ACCEPTANCE.md).

## Local setup

Python 3.12 is the initial tested baseline. From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
python -m playwright install chromium
mkdir -p data
export DATABASE_URL=sqlite:///./data/notes.db
export LOCAL_AI_NOTES_COOKIE_SECURE=false
alembic upgrade head
notes create-owner --username owner
uvicorn local_ai_notes.main:create_app --factory --host 127.0.0.1
```

Open `http://127.0.0.1:8000/login`. `LOCAL_AI_NOTES_COOKIE_SECURE=false` is only for explicit local HTTP development. Secure cookies are the default; leave them enabled behind HTTPS/Tailscale Serve or another trusted TLS endpoint. Environment files are examples and are not automatically loaded.

PowerShell: activate with `.venv\Scripts\Activate.ps1`, install the browser with `python -m playwright install chromium`, create `data` with `New-Item -ItemType Directory -Force data`, set `$env:DATABASE_URL='sqlite:///./data/notes.db'`, and set `$env:LOCAL_AI_NOTES_COOKIE_SECURE='false'` only for local HTTP development.

The administrative commands prompt twice without echoing the password. Initial passwords require 12-1024 characters and are hashed using Argon2id. Bootstrap creates one normalized owner account and Inbox atomically. Local password recovery uses `notes reset-password --username owner`; a successful reset revokes every existing browser session. `notes rebuild-search` reconstructs derived FTS state only.

## Backup and recovery

Stage 6 installs a separate `notes-recovery` administrative entry point. Backup creation is safe while the application is running because it uses SQLite's backup API. Restore is an offline operation: stop the application before replacing an existing configured database.

```sh
notes-recovery backup /safe/path/local-ai-notes-backup.sqlite
notes-recovery verify-backup /safe/path/local-ai-notes-backup.sqlite
notes-recovery restore /safe/path/local-ai-notes-backup.sqlite --confirm-replace
alembic upgrade head
notes rebuild-search
```

Successful backup/verification prints a SHA-256 digest and schema/project/note/revision counts. Existing backup destinations require `--overwrite`. Existing restore targets require `--confirm-replace`; a confirmed replacement first creates a timestamped pre-restore safety backup. Restored sessions are revoked automatically, so log in again after recovery. See [Backup and Restore](BACKUP_RESTORE.md) for Docker and OMV/Pi procedures.

## Export and history behavior

Exports are generated on demand from committed active content. Note export downloads Markdown with YAML frontmatter. Project/workspace export downloads a temporary ZIP containing `manifest.json` and UUID-named Markdown notes; temporary archives are removed after response completion. Workspace manifests preserve empty projects and Inbox identity. Exports are not backups: trash, full history, credentials, sessions and other complete application state are excluded.

Retained revisions are listed in History. Historical title/body content is available through an authenticated read-only endpoint and the History viewer; viewing does not alter the current note. Restoring historical content remains a separate explicit mutation that creates a new revision.

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
- Export reads are session-authenticated and owner-scoped; filenames/archive paths are generated from canonical UUIDs rather than user titles.
- Historical revision reads are session-authenticated and constrained to revisions belonging to the requested owned note.
- Backup/restore is CLI/admin-only and never exposed as a browser write surface.
- The login throttle is intentionally in-process for the single-process initial deployment.

## Health and verification

- `/health/live` reports that the process responds.
- `/health/ready` returns 200 only when the database is reachable at schema 0002; otherwise 503 without database details.
- Run `pytest -q` for the full service/API/recovery/browser acceptance suite. The browser smoke test executes when Playwright Chromium is installed; otherwise that test is skipped locally.
- CI installs Chromium and therefore requires the real-browser acceptance smoke test to run.
- CI performs `pip check`, audits `requirements.lock` with `pip-audit`, builds the locked Docker image, migrates an empty named volume, starts the container and probes readiness.

Readiness remains at migration 0002 because Stages 5-7 add no persistent schema. Backup verification is an explicit administrative operation, not part of every readiness request. Destructive downgrades remain disabled.

## Dependency and release limits

`pyproject.toml` contains the human-maintained compatible dependency ranges. `requirements.lock` records the exact production resolution used by the v0.0.1 Docker image; Docker installs that file before installing the application with dependency resolution disabled. The lock is intentionally refreshed only during dependency review, and CI checks that every direct runtime dependency remains represented by an exact pin.

The current lock pins versions but does not contain package hashes. Do not claim hash-level supply-chain reproducibility. CI performs a vulnerability audit of the locked production set, and any reported issue must be triaged before a release candidate is approved.
