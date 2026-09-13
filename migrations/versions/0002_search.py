"""Add rebuildable FTS5 index for active current note content."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE VIRTUAL TABLE note_search USING fts5(
        note_id UNINDEXED,
        title,
        body_markdown,
        tokenize='unicode61'
    )""")
    op.execute("""INSERT INTO note_search(note_id,title,body_markdown)
        SELECT n.id,r.title,r.body_markdown
        FROM notes n JOIN note_revisions r ON r.id=n.current_revision_id
        WHERE n.deleted_at IS NULL""")


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup instead")
