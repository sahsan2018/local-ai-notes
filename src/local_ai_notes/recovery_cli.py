"""Command handlers for backup and recovery administration."""
from .backup import create_backup, verify_backup
from .restore import restore_backup


def print_backup(info):
    print(f"Backup valid: {info['path']}")
    print(f"Schema: {info['schema_version']}")
    print(f"Projects: {info['projects']}  Notes: {info['notes']}  Revisions: {info['revisions']}")
    print(f"SHA-256: {info['sha256']}")


def run_backup(destination, overwrite=False):
    print_backup(create_backup(destination, overwrite=overwrite))


def run_verify(source):
    print_backup(verify_backup(source))


def run_restore(source, confirm_replace=False):
    result = restore_backup(source, confirm_replace=confirm_replace)
    print(f"Database restored and verified: {result['restored']['path']}")
    print(f"SHA-256: {result['restored']['sha256']}")
    if result["safety_backup"]:
        print(f"Pre-restore safety backup: {result['safety_backup']}")
    print("All restored sessions were revoked. Run alembic upgrade head before restarting the application.")


COMMANDS = {
    "backup": run_backup,
    "verify-backup": run_verify,
    "restore": run_restore,
}
