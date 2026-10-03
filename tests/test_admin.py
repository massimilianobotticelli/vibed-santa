import json

import pytest
from tinydb import TinyDB

from admin import admin_exists, create_admin, verify_admin, verify_admin_password


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "secret_santa.db"


@pytest.fixture
def db(db_path):
    db = TinyDB(db_path)
    yield db
    db.close()


def test_no_admin_on_first_start(db):
    assert not admin_exists(db)
    assert not verify_admin(db, "admin", "secret")


def test_admin_can_log_in_after_creation(db):
    create_admin(db, "admin", "secret")

    assert admin_exists(db)
    assert verify_admin(db, "admin", "secret")


def test_wrong_credentials_are_rejected(db):
    create_admin(db, "admin", "secret")

    assert not verify_admin(db, "admin", "wrong")
    assert not verify_admin(db, "someone", "secret")


def test_password_is_not_stored_in_plain_text(db, db_path):
    create_admin(db, "admin", "secret")

    assert "secret" not in json.dumps(json.loads(db_path.read_text()))


def test_only_one_admin_can_be_created(db):
    create_admin(db, "admin", "secret")

    with pytest.raises(ValueError):
        create_admin(db, "intruder", "secret")
    assert verify_admin(db, "admin", "secret")


def test_verify_admin_password(db):
    assert not verify_admin_password(db, "secret")

    create_admin(db, "admin", "secret")

    assert verify_admin_password(db, "secret")
    assert not verify_admin_password(db, "wrong")
