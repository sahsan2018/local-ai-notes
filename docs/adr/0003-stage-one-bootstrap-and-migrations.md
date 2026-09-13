# ADR-0003: Stage-one bootstrap and migration implementation

- Status: Proposed in stage-one draft PR
- Decision owners: project owner

## Context

The first implementation must enforce single-owner setup and note/revision integrity before browser access exists.

## Decision

Use Python 3.12, FastAPI, SQLAlchemy connections and explicit Alembic SQLite migrations. Use a local administrative command with hidden password prompts and Argon2id hashing. Serialize bootstrap with BEGIN IMMEDIATE; database constraints additionally enforce one owner and one Inbox. Record owner/Inbox setup in the same transaction.

Initial revisions are immutable and non-deletable through SQLite triggers. Deferred composite foreign keys permit atomic note/first-revision insertion. Later retention work must deliberately migrate deletion rules. Destructive migration downgrade is disabled pending a tested recovery process.

Docker runs as a non-root UID, publishes loopback only and uses persistent volume storage. Health readiness verifies migration version, not login readiness or available write capacity. Authentication endpoints and domain operations remain later-stage work.

## Consequences

SQL is SQLite-specific and schema expansion requires migrations. Multi-user support would require removing the single-owner unique constraint. Dependency ranges remain unlocked in this development draft; release reproducibility and Pi hardware validation remain release work.

## Alternatives considered

- Public first-user registration: risks an unintended visitor claiming ownership.
- Migrations at request/startup time: obscures deployment control and concurrent startup behavior.
- Password in command arguments: can expose credentials in history/process listings.
