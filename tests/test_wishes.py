import pytest
from tinydb import TinyDB

from wishes import WISHES_TABLE, get_wish_list, migrate_legacy_wishes, save_wish_list


@pytest.fixture
def db(tmp_path):
    db = TinyDB(tmp_path / "secret_santa.db")
    yield db
    db.close()


@pytest.fixture
def config():
    # "max" belongs to both families, like someone joining their partner's family
    return {
        "families": [
            {
                "id": "botticelli",
                "participants": [{"username": "max"}, {"username": "anna"}],
            },
            {
                "id": "rossi",
                "participants": [{"username": "max"}, {"username": "giulia"}],
            },
        ]
    }


def test_wish_list_is_not_visible_in_other_groups(db):
    save_wish_list(db, "botticelli", "max", ["Book"])

    assert get_wish_list(db, "botticelli", "max") == ["Book"]
    assert get_wish_list(db, "rossi", "max") == []


def test_each_group_keeps_its_own_wish_list(db):
    save_wish_list(db, "botticelli", "max", ["Book"])
    save_wish_list(db, "rossi", "max", ["Scarf"])

    assert get_wish_list(db, "botticelli", "max") == ["Book"]
    assert get_wish_list(db, "rossi", "max") == ["Scarf"]


def test_save_overwrites_only_the_same_group(db):
    save_wish_list(db, "botticelli", "max", ["Book"])
    save_wish_list(db, "rossi", "max", ["Scarf"])
    save_wish_list(db, "botticelli", "max", ["Book", "Mug"])

    assert get_wish_list(db, "botticelli", "max") == ["Book", "Mug"]
    assert get_wish_list(db, "rossi", "max") == ["Scarf"]
    assert len(db.table(WISHES_TABLE)) == 2


def test_missing_wish_list_is_empty(db):
    assert get_wish_list(db, "botticelli", "anna") == []


def test_migration_copies_legacy_list_into_every_group_of_the_user(db, config):
    db.table(WISHES_TABLE).insert({"username": "max", "items": ["Book"]})
    db.table(WISHES_TABLE).insert({"username": "anna", "items": ["Tea"]})

    assert migrate_legacy_wishes(db, config) == 2

    assert get_wish_list(db, "botticelli", "max") == ["Book"]
    assert get_wish_list(db, "rossi", "max") == ["Book"]
    assert get_wish_list(db, "botticelli", "anna") == ["Tea"]
    assert get_wish_list(db, "rossi", "anna") == []
    assert len(db.table(WISHES_TABLE)) == 3


def test_migration_does_not_overwrite_existing_group_list(db, config):
    db.table(WISHES_TABLE).insert({"username": "max", "items": ["Book"]})
    save_wish_list(db, "rossi", "max", ["Scarf"])

    migrate_legacy_wishes(db, config)

    assert get_wish_list(db, "botticelli", "max") == ["Book"]
    assert get_wish_list(db, "rossi", "max") == ["Scarf"]


def test_migration_keeps_lists_of_users_not_in_any_group(db, config):
    db.table(WISHES_TABLE).insert({"username": "ghost", "items": ["Chain"]})

    assert migrate_legacy_wishes(db, config) == 0
    assert len(db.table(WISHES_TABLE)) == 1


def test_migration_is_idempotent(db, config):
    db.table(WISHES_TABLE).insert({"username": "max", "items": ["Book"]})

    assert migrate_legacy_wishes(db, config) == 1
    assert migrate_legacy_wishes(db, config) == 0
    assert len(db.table(WISHES_TABLE)) == 2
