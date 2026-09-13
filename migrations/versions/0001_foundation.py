"""Initial SQLite schema. No application mutations are exposed yet."""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        """CREATE TABLE users (
            id TEXT PRIMARY KEY NOT NULL, username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL, created_at TEXT NOT NULL)""",
        "CREATE UNIQUE INDEX single_owner ON users ((1))",
        """CREATE TABLE sessions (
            id TEXT PRIMARY KEY NOT NULL, user_id TEXT NOT NULL REFERENCES users(id),
            token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL, revoked_at TEXT)""",
        """CREATE TABLE projects (
            id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL REFERENCES users(id),
            name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 200),
            description TEXT NOT NULL DEFAULT '' CHECK(length(description)<=2000),
            is_inbox INTEGER NOT NULL DEFAULT 0 CHECK(is_inbox IN (0,1)),
            version INTEGER NOT NULL CHECK(version>=1), created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, UNIQUE(owner_id,id))""",
        "CREATE UNIQUE INDEX one_inbox ON projects(owner_id) WHERE is_inbox=1",
        """CREATE TABLE notes (
            id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL REFERENCES users(id),
            project_id TEXT NOT NULL, current_revision_id TEXT NOT NULL,
            version INTEGER NOT NULL CHECK(version>=1),
            next_revision_number INTEGER NOT NULL CHECK(next_revision_number>=2),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
            FOREIGN KEY(owner_id,project_id) REFERENCES projects(owner_id,id),
            FOREIGN KEY(id,current_revision_id) REFERENCES note_revisions(note_id,id)
                DEFERRABLE INITIALLY DEFERRED)""",
        """CREATE TABLE note_revisions (
            id TEXT PRIMARY KEY NOT NULL, note_id TEXT NOT NULL REFERENCES notes(id),
            revision_number INTEGER NOT NULL CHECK(revision_number>=1),
            title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 200),
            content_format TEXT NOT NULL CHECK(content_format='markdown'),
            content_schema_version INTEGER NOT NULL CHECK(content_schema_version=1),
            body_markdown TEXT NOT NULL CHECK(length(CAST(body_markdown AS BLOB))<=1048576),
            actor_type TEXT NOT NULL, actor_id TEXT NOT NULL, source_type TEXT NOT NULL,
            request_id TEXT NOT NULL, created_at TEXT NOT NULL, restored_from_revision_id TEXT,
            UNIQUE(note_id,id), UNIQUE(note_id,revision_number),
            FOREIGN KEY(note_id,restored_from_revision_id) REFERENCES note_revisions(note_id,id))""",
        """CREATE TRIGGER revisions_immutable BEFORE UPDATE ON note_revisions
            BEGIN SELECT RAISE(ABORT, 'Revisions are immutable'); END""",
        """CREATE TRIGGER revisions_retained BEFORE DELETE ON note_revisions
            BEGIN SELECT RAISE(ABORT, 'Revision deletion is not supported'); END""",
        """CREATE TABLE audit_events (
            id TEXT PRIMARY KEY NOT NULL, note_id TEXT REFERENCES notes(id),
            project_id TEXT REFERENCES projects(id), event_type TEXT NOT NULL,
            actor_type TEXT NOT NULL, actor_id TEXT NOT NULL, request_id TEXT NOT NULL,
            created_at TEXT NOT NULL, details_schema_version INTEGER NOT NULL,
            details_json TEXT NOT NULL CHECK(json_valid(details_json)))""",
        """CREATE TABLE mutation_receipts (
            actor_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, operation TEXT NOT NULL,
            request_hash TEXT NOT NULL, result_json TEXT NOT NULL CHECK(json_valid(result_json)),
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            PRIMARY KEY(actor_id,idempotency_key))""",
        "CREATE INDEX notes_listing ON notes(owner_id,project_id,deleted_at,updated_at,id)",
        "CREATE INDEX session_owner ON sessions(user_id)",
        "CREATE INDEX receipt_expiry ON mutation_receipts(expires_at)",
        "CREATE INDEX audit_note ON audit_events(note_id,created_at)",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup instead")
