"""Admin account storage.

There is a single admin account, created from the app on its first start.
Only a salted hash of the password is stored.
"""

import hashlib
import hmac
import os
import threading

from tinydb import TinyDB

ADMIN_TABLE = "admin"
_HASH_ITERATIONS = 600_000

# Streamlit serves every session from the same process: make sure two people
# opening the app at the same time cannot both create an admin account
_create_lock = threading.Lock()


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _HASH_ITERATIONS
    ).hex()


def admin_exists(db: TinyDB) -> bool:
    """Check whether the admin account has been created"""
    return len(db.table(ADMIN_TABLE)) > 0


def create_admin(db: TinyDB, username: str, password: str):
    """Create the admin account

    Raises:
        ValueError: If the admin account already exists
    """
    with _create_lock:
        if admin_exists(db):
            raise ValueError("The admin account already exists")

        salt = os.urandom(16)
        db.table(ADMIN_TABLE).insert(
            {
                "username": username,
                "salt": salt.hex(),
                "password_hash": _hash_password(password, salt),
            }
        )


def verify_admin(db: TinyDB, username: str, password: str) -> bool:
    """Check the admin credentials"""
    records = db.table(ADMIN_TABLE).all()
    if not records:
        return False

    return records[0]["username"] == username and verify_admin_password(db, password)


def verify_admin_password(db: TinyDB, password: str) -> bool:
    """Check the admin password, e.g. to confirm a dangerous action"""
    records = db.table(ADMIN_TABLE).all()
    if not records:
        return False

    record = records[0]
    password_hash = _hash_password(password, bytes.fromhex(record["salt"]))
    return hmac.compare_digest(record["password_hash"], password_hash)
