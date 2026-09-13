# v0.0.1 manual acceptance runbook

Use this only after Stage 7 CI is green. Record the tested commit and every result in [V0_0_1_ACCEPTANCE.md](V0_0_1_ACCEPTANCE.md). Use synthetic notes until the release gate is satisfied.

## 1. Freeze the candidate

Record:

- Git commit SHA;
- Raspberry Pi model and OS/architecture;
- Docker and Docker Compose versions;
- browser/OS used for desktop testing;
- phone/browser used for mobile testing;
- Tailscale version and access method.

Do not mix results from different commits without recording the change and rerunning affected checks.

## 2. Pi / OMV deployment

Clone the repository and check out the Stage 7 candidate branch. Use an OMV-managed directory on locally attached storage for `/data`; do not place the active SQLite database on SMB.

Create a local, uncommitted Compose override that bind-mounts the chosen data directory to `/data`. Ensure the directory is writable by container UID 10001.

Then run:

```sh
docker compose build
docker compose run --rm app alembic upgrade head
docker compose run --rm app notes create-owner --username owner
docker compose up -d --wait
curl --fail http://127.0.0.1:8000/health/ready
```

Record whether the ARM64 image builds, migrations/bootstrap succeed, the container is healthy, and the OMV directory contains the SQLite database and its normal SQLite sidecar files while in use.

## 3. Create synthetic acceptance data

Through the browser create:

- a renamed Inbox;
- at least two additional projects, including one empty project;
- an active note with Unicode in title/body and at least three saved revisions;
- a second note moved between projects;
- a note with duplicate title text;
- a note moved to Trash;
- content containing a unique search phrase.

Exercise Markdown preview and note/project/workspace export. Do not use irreplaceable notes during acceptance.

## 4. Desktop and keyboard workflow

Without relying on the mouse for the primary path, verify:

1. login;
2. project selection;
3. note creation;
4. title/body editing;
5. toolbar controls;
6. Ctrl/Cmd+S save;
7. visible Unsaved/Saving/Saved or failure state;
8. search and result opening;
9. historical revision View and Restore as separate actions;
10. Trash and restore;
11. export controls;
12. logout.

Confirm focus remains visible, Tab order is understandable, no keyboard trap appears, and the historical viewer is clearly read-only.

## 5. Real phone workflow

On a phone browser, repeat login, project selection, note creation/edit/save, search, history viewing, trash/restore and logout. Verify the software keyboard does not make the editor unusable, controls do not overlap, and no persistent horizontal page scrolling is required.

## 6. Tailscale HTTPS path

Access the same Pi through the intended Tailscale HTTPS/Serve endpoint with secure cookies left enabled. Verify:

- login and session persistence across refresh;
- save/move/trash/restore writes succeed through CSRF protection;
- note/project/workspace downloads work;
- logout ends the session;
- a password reset invalidates an already-open remote session;
- the application port is not intentionally exposed directly to the public Internet.

Repeat at least one phone test while away from the home LAN so traffic is actually using the tailnet path.

## 7. Persistence

With the synthetic dataset in place:

```sh
docker compose restart
```

Verify projects, IDs, revisions, memberships, Trash and search remain intact. Then reboot the Pi and repeat the same verification after the stack returns.

## 8. Real backup and separate restore rehearsal

Mount a backup directory from a different suitable storage location into a one-off container and create/verify a backup as documented in [BACKUP_RESTORE.md](BACKUP_RESTORE.md). Record its SHA-256.

Restore the backup into a **separate** database file rather than replacing the active acceptance database. One pattern is to override `DATABASE_URL` for the recovery commands so the restored target is another file under `/data`.

After restore:

```sh
alembic upgrade head
notes rebuild-search
```

using the restored database URL. Start a temporary app instance on a different local port against the restored database and verify:

- owner/password still works;
- pre-backup browser session is not accepted by the restored instance;
- project and Inbox IDs match;
- empty project exists;
- active and trashed notes exist;
- project membership matches;
- revision counts/content/lineage match;
- search returns the expected unique phrase after rebuild.

Keep the production acceptance database untouched during this rehearsal.

## 9. Safe failure checks

Confirm that:

- backup refuses an existing destination unless overwrite is explicitly requested;
- an invalid backup fails verification;
- restore to an existing target refuses replacement without explicit confirmation;
- a failed browser save leaves the typed draft visible when a safe failure can be simulated without risking the acceptance database.

Do not deliberately corrupt the active acceptance database or interrupt power during a SQLite write.

## 10. Fresh-install documentation check

Using a fresh checkout and an empty, separate data directory, follow the documented setup literally: build, migrate, bootstrap, start, login, create/edit/search/export, backup and clean shutdown. Any undocumented prerequisite is a release-documentation defect.

## Result recording

For each manual scenario record:

- PASS / FAIL;
- date;
- commit SHA;
- device/browser/runtime versions;
- short evidence or observed behavior;
- any defect/PR commit used to fix a failure.

A required manual scenario left untested remains a release blocker; CI success alone does not change it to PASS.
