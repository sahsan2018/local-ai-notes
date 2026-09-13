"""Derived full-text search helpers. Canonical note data remains in normal tables."""
import hashlib

from sqlalchemy import text

MAX_QUERY_BYTES = 500
MAX_QUERY_TERMS = 32
HIT_START = "[[LAN_HIT_START]]"
HIT_END = "[[LAN_HIT_END]]"


def normalize_search_query(query):
    if not isinstance(query, str):
        raise ValueError("Search query must be text")
    normalized = " ".join(query.split())
    if len(normalized.encode("utf-8")) > MAX_QUERY_BYTES:
        raise ValueError("Search query is too large")
    terms = normalized.split()
    if len(terms) > MAX_QUERY_TERMS:
        raise ValueError("Search query has too many terms")
    quoted = []
    for term in terms:
        quoted.append('"' + term.replace('"', '""') + '"')
    return normalized, " AND ".join(quoted)


def query_fingerprint(normalized_query):
    return hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()


def strip_hit_markers(value):
    return (value or "").replace(HIT_START, "").replace(HIT_END, "")


def rebuild_search_index(engine):
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            connection.execute(text("DELETE FROM note_search"))
            connection.execute(text("""INSERT INTO note_search(note_id,title,body_markdown)
                SELECT n.id,r.title,r.body_markdown
                FROM notes n JOIN note_revisions r ON r.id=n.current_revision_id
                WHERE n.deleted_at IS NULL"""))
            count = connection.execute(text("SELECT count(*) FROM note_search")).scalar_one()
            connection.commit()
            return count
        except Exception:
            connection.rollback()
            raise
