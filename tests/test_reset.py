import json

import pytest
from tinydb import TinyDB

import groups
from admin import admin_exists, create_admin
from draws import get_draw, run_draw
from reset import backup, reset_all, reset_round
from wishes import get_wish_list, save_wish_list


@pytest.fixture
def db_file(tmp_path):
    return tmp_path / "secret_santa.db"


@pytest.fixture
def db(db_file):
    db = TinyDB(db_file)
    create_admin(db, "admin", "secret")
    for name in ("alice", "bob"):
        groups.add_person(db, name, username=name)
    groups.add_group(db, "Smith", 30, "€", ["alice", "bob"])
    run_draw(db, groups.build_config(db)["families"][0])
    save_wish_list(db, "smith", "alice", ["Book"])
    yield db
    db.close()


def test_reset_round_keeps_admin_groups_and_people(db):
    reset_round(db)

    assert get_draw(db, "smith") is None
    assert get_wish_list(db, "smith", "alice") == []
    assert admin_exists(db)
    assert groups.get_group(db, "smith")["members"] == ["alice", "bob"]
    assert groups.get_person(db, "alice") is not None


def test_reset_all_deletes_everything(db):
    reset_all(db)

    assert not admin_exists(db)
    assert groups.list_people(db) == []
    assert groups.list_groups(db) == []
    assert get_draw(db, "smith") is None


def test_backup_keeps_a_copy_of_the_data(db, db_file):
    backup_file = backup(db_file)
    reset_all(db)

    assert backup_file.parent == db_file.parent
    assert backup_file.name.startswith("secret_santa.") and backup_file.suffix == ".db"
    restored = TinyDB(backup_file)
    assert admin_exists(restored)
    assert get_wish_list(restored, "smith", "alice") == ["Book"]
    restored.close()
    assert json.loads(db_file.read_text()) == {}


def test_backups_never_overwrite_each_other(db, db_file):
    first = backup(db_file)
    reset_round(db)
    second = backup(db_file)

    assert first != second
    assert get_wish_list(TinyDB(first), "smith", "alice") == ["Book"]
