import argparse
from datetime import datetime, timezone
from getpass import getpass
from uuid import uuid4

from argon2 import PasswordHasher
from sqlalchemy import text

from .auth import reset_password
from .db import database_engine
from .search import rebuild_search_index


def create_owner(engine, username, password):
    username = username.strip().casefold()
    if not username or len(username) > 200:
        raise ValueError("Username must contain 1-200 characters")
    if not 12 <= len(password) <= 1024:
        raise ValueError("Password must contain 12-1024 characters")
    password_hash = PasswordHasher().hash(password)
    owner, project = str(uuid4()), str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            if connection.execute(text("SELECT 1 FROM users LIMIT 1")).first():
                raise ValueError("Owner already exists")
            connection.execute(text("INSERT INTO users VALUES (:id, :name, :hash, :now)"),
                               {"id": owner, "name": username, "hash": password_hash, "now": now})
            connection.execute(text("INSERT INTO projects VALUES (:id, :owner, 'Inbox', '', 1, 1, :now, :now)"),
                               {"id": project, "owner": owner, "now": now})
            connection.execute(text("""INSERT INTO audit_events
                (id, project_id, event_type, actor_type, actor_id, request_id, created_at, details_schema_version, details_json)
                VALUES (:id, :project, 'owner_bootstrapped', 'user', :owner, :request, :now, 1, '{}')"""),
                               {"id": str(uuid4()), "project": project, "owner": owner,
                                "request": str(uuid4()), "now": now})
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return owner


def _password_pair(parser):
    password = getpass("Password: ")
    if password != getpass("Confirm password: "):
        parser.exit(1, "Passwords do not match\n")
    return password


def main():
    parser = argparse.ArgumentParser(description="Local administrative commands")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-owner")
    create.add_argument("--username", required=True)
    reset = sub.add_parser("reset-password")
    reset.add_argument("--username", required=True)
    sub.add_parser("rebuild-search")
    args = parser.parse_args()
    engine = database_engine()
    try:
        if args.command == "rebuild-search":
            count = rebuild_search_index(engine)
            print(f"Search index rebuilt: {count} active notes indexed.")
            return
        password = _password_pair(parser)
        if args.command == "create-owner":
            create_owner(engine, args.username, password)
            print("Owner and Inbox created.")
        else:
            reset_password(engine, args.username, password)
            print("Password reset and existing sessions revoked.")
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    finally:
        engine.dispose()
