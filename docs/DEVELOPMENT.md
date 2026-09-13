# Development

This branch implements the storage foundation and [internal stage 2 application services](STAGE_2.md). There is no notebook UI, browser login, session issuance, HTTP note API, search or AI yet. Session storage is prepared for subsequent work. The complete v0.0.1 milestone remains unfinished.

## Local setup

Python 3.12 is the initial tested baseline. From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
mkdir -p data
export DATABASE_URL=sqlite:///./data/notes.db
alembic upgrade head
notes create-owner --username owner
uvicorn local_ai_notes.main:create_app --factory --host 127.0.0.1
```

PowerShell: activate with `.venv\Scripts\Activate.ps1`, create `data` with `New-Item -ItemType Directory -Force data`, and set `$env:DATABASE_URL='sqlite:///./data/notes.db'`. The remaining Python/Alembic commands are the same. Environment files are examples, not automatically loaded.

The administrative command prompts twice without echoing the password. Do not pass passwords in arguments or commit them. Initial passwords require 12-1024 characters and are hashed using Argon2id. Bootstrap creates one normalized owner account and Inbox atomically; repeated calls fail without mutation. Password recovery and browser authentication are subsequent stages.

## Docker setup

```sh
docker compose build
docker compose run --rm app alembic upgrade head
docker compose run --rm app notes create-owner --username owner
docker compose up -d --wait
```

Only loopback port 8000 is published. The container runs as UID 10001 and uses a named volume at /data. Migrations are explicit and never run during a health request or automatically at server startup. Run Compose from the repository root. Do not use `docker compose down -v` on data you want to retain.

A later Pi deployment can use an OMV bind mount owned by UID 10001 with appropriate permissions. Keep the database on a locally mounted disk, not SMB. Do not open the port publicly. Exact host paths and Tailscale configuration are not needed for this PR. ARM64/Pi execution still requires an on-device check before real use.

## Health and verification

- /health/live reports that the process responds.
- /health/ready returns 200 only when the database is reachable at schema 0001; otherwise 503 without database details. It does not promise sufficient disk space, write access, owner setup or backup health.
- Run `pytest -q` for migrations, constraints, bootstrap rollback, persistence and health checks.
- CI also builds and starts the Docker image after migrating an empty named volume.

Readiness must be updated when the migration head changes. The initial migration is SQLite-specific, uses deferred current-revision constraints and prohibits revision update/deletion. Destructive downgrades are deliberately disabled; use verified backups for recovery. This is not yet a tested end-user backup/restore workflow.

## Dependency and release limits

Dependencies have bounded version ranges, not a production lockfile. CI resolves them on each run. Add a reproducible release lock and perform dependency/security review before packaging a stable release. Initial SQLAlchemy use is connection/transaction based; domain services and ORM mappings can evolve in stage 2 without exposing raw SQL to clients.
