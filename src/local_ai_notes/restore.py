"""Offline restore workflow for verified Local AI Notes SQLite backups."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from .backup import RecoveryError, create_backup, database_path, verify_backup


def _assert_target_offline(path):
    if not path.exists():
        return
    try:
        connection = sqlite3.connect(path, timeout=0.1)
        try:
            connection.execute("BEGIN EXCLUSIVE")
            connection.rollback()
        finally:
            connection.close()
    except sqlite3.OperationalError as error:
        raise RecoveryError("Target database appears to be in use; stop the application before restore") from error


def _safety_path(target):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return target.with_name(f"{target.name}.pre-restore-{stamp}.sqlite")


def restore_backup(source, database_url=None, confirm_replace=False, revoke_sessions=True):
    source = Path(source).expanduser().resolve()
    source_info = verify_backup(source)
    target = database_path(database_url)
    if source == target:
        raise RecoveryError("Restore source must differ from the target database")
    if not target.parent.is_dir():
        raise RecoveryError("Target database directory does not exist")
    if target.exists() and not confirm_replace:
        raise RecoveryError("Target database exists; rerun with --confirm-replace after stopping the application")
    _assert_target_offline(target)

    safety_backup = None
    if target.exists():
        safety_backup = _safety_path(target)
        create_backup(safety_backup, f"sqlite:///{target}")

    try:
        source_connection = sqlite3.connect(source, timeout=5)
        target_connection = sqlite3.connect(target, timeout=5)
        try:
            source_connection.backup(target_connection)
            if revoke_sessions:
                target_connection.execute(
                    "UPDATE sessions SET revoked_at=? WHERE revoked_at IS NULL",
                    (datetime.now(timezone.utc).isoformat(),),
                )
            target_connection.commit()
        finally:
            target_connection.close()
            source_connection.close()
    except sqlite3.DatabaseError as error:
        raise RecoveryError("Backup could not be restored") from error

    restored = verify_backup(target)
    return {
        "source": source_info,
        "restored": restored,
        "safety_backup": str(safety_backup) if safety_backup else None,
        "sessions_revoked": bool(revoke_sessions),
    }
