import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

SESSION_DAYS = 7
SESSION_COOKIE = "lan_session"
LOGIN_CSRF_COOKIE = "lan_login_csrf"


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(engine, username, password):
    username = username.strip().casefold()
    now = datetime.now(timezone.utc)
    try:
        with engine.connect() as c:
            user = c.execute(text("SELECT * FROM users WHERE username=:username"), {"username": username}).mappings().first()
            if user is None:
                return None
            try:
                valid = PasswordHasher().verify(user["password_hash"], password)
            except (VerifyMismatchError, InvalidHashError):
                return None
            if not valid:
                return None
            raw = secrets.token_urlsafe(32)
            c.execute(text("INSERT INTO sessions VALUES (:id,:user,:token,:now,:expires,NULL)"), {
                "id": str(uuid4()), "user": user["id"], "token": token_hash(raw),
                "now": now.isoformat(), "expires": (now + timedelta(days=SESSION_DAYS)).isoformat(),
            })
            c.commit()
            return {"token": raw, "user_id": user["id"], "expires_at": (now + timedelta(days=SESSION_DAYS))}
    except OperationalError:
        return None


def authenticated_user(engine, raw_token):
    if not raw_token:
        return None
    now = datetime.now(timezone.utc).isoformat()
    try:
        with engine.connect() as c:
            return c.execute(text("""SELECT u.id,u.username,s.id AS session_id,s.expires_at
                FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=:token AND s.revoked_at IS NULL AND s.expires_at>:now"""),
                {"token": token_hash(raw_token), "now": now}).mappings().first()
    except OperationalError:
        return None


def revoke_session(engine, raw_token):
    if not raw_token:
        return
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as c:
        c.execute(text("UPDATE sessions SET revoked_at=:now WHERE token_hash=:token AND revoked_at IS NULL"),
                  {"now": now, "token": token_hash(raw_token)})


def reset_password(engine, username, password):
    username = username.strip().casefold()
    if not username or len(username) > 200:
        raise ValueError("Unknown owner")
    if not 12 <= len(password) <= 1024:
        raise ValueError("Password must contain 12-1024 characters")
    now = datetime.now(timezone.utc).isoformat()
    with engine.connect() as c:
        c.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            user = c.execute(text("SELECT id FROM users WHERE username=:username"), {"username": username}).mappings().first()
            if user is None:
                raise ValueError("Unknown owner")
            c.execute(text("UPDATE users SET password_hash=:hash WHERE id=:id"),
                      {"hash": PasswordHasher().hash(password), "id": user["id"]})
            c.execute(text("UPDATE sessions SET revoked_at=:now WHERE user_id=:id AND revoked_at IS NULL"),
                      {"now": now, "id": user["id"]})
            c.execute(text("""INSERT INTO audit_events
                (id,event_type,actor_type,actor_id,request_id,created_at,details_schema_version,details_json)
                VALUES (:event,'password_reset','user',:actor,:request,:now,1,'{}')"""),
                      {"event": str(uuid4()), "actor": user["id"], "request": str(uuid4()), "now": now})
            c.commit()
        except Exception:
            c.rollback()
            raise
