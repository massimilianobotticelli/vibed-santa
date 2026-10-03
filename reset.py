"""Resetting the app data, from the admin console.

Every reset is preceded by a backup of the database file, so a reset by
mistake can be undone by restoring the backup.
"""

import shutil
from datetime import datetime
from pathlib import Path

from tinydb import TinyDB

from draws import DRAWS_TABLE
from wishes import WISHES_TABLE


def backup(db_file: Path) -> Path:
    """Copy the database file next to it, with a timestamp in the name

    Returns:
        Path of the backup
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_file = db_file.with_name(f"{db_file.stem}.{timestamp}.bak{db_file.suffix}")
    n = 2
    while backup_file.exists():
        # Never overwrite an earlier backup made within the same second
        backup_file = db_file.with_name(
            f"{db_file.stem}.{timestamp}-{n}.bak{db_file.suffix}"
        )
        n += 1
    shutil.copy2(db_file, backup_file)
    return backup_file


def reset_round(db: TinyDB):
    """Start a new Secret Santa round: delete all draws and wish lists,
    keeping the admin account, groups and people"""
    db.drop_table(DRAWS_TABLE)
    db.drop_table(WISHES_TABLE)


def reset_all(db: TinyDB):
    """Delete all data, including the admin account"""
    db.drop_tables()
