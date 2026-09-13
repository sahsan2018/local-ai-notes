import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url


def database_engine(url=None):
    url = url or os.environ.get("DATABASE_URL", "sqlite:///./data/notes.db")
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite" or not parsed.database:
        raise ValueError("A file-backed SQLite DATABASE_URL is required")
    if parsed.database == ":memory:":
        raise ValueError("Use a file-backed database for persistence")
    engine = create_engine(url, connect_args={"timeout": 5}, hide_parameters=True)

    @event.listens_for(engine, "connect")
    def configure(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")

    return engine
