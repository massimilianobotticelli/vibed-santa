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
    # "alice" belongs to both families, like someone joining their partner's family
    return {
        "families": [
            {
                "id": "smith",
                "participants": [{"username": "alice"}, {"username": "bob"}],
            },
            {
                "id": "jones",
                "participants": [{"username": "alice"}, {"username": "carol"}],
            },
        ]
    }


def test_wish_list_is_not_visible_in_other_groups(db):
    save_wish_list(db, "smith", "alice", ["Book"])

    assert get_wish_list(db, "smith", "alice") == ["Book"]
    assert get_wish_list(db, "jones", "alice") == []


def test_each_group_keeps_its_own_wish_list(db):
    save_wish_list(db, "smith", "alice", ["Book"])
    save_wish_list(db, "jones", "alice", ["Scarf"])

    assert get_wish_list(db, "smith", "alice") == ["Book"]
    assert get_wish_list(db, "jones", "alice") == ["Scarf"]


def test_save_overwrites_only_the_same_group(db):
    save_wish_list(db, "smith", "alice", ["Book"])
    save_wish_list(db, "jones", "alice", ["Scarf"])
    save_wish_list(db, "smith", "alice", ["Book", "Mug"])

    assert get_wish_list(db, "smith", "alice") == ["Book", "Mug"]
    assert get_wish_list(db, "jones", "alice") == ["Scarf"]
    assert len(db.table(WISHES_TABLE)) == 2


def test_missing_wish_list_is_empty(db):
    assert get_wish_list(db, "smith", "bob") == []


def test_migration_copies_legacy_list_into_every_group_of_the_user(db, config):
    db.table(WISHES_TABLE).insert({"username": "alice", "items": ["Book"]})
    db.table(WISHES_TABLE).insert({"username": "bob", "items": ["Tea"]})

    assert migrate_legacy_wishes(db, config) == 2

    assert get_wish_list(db, "smith", "alice") == ["Book"]
    assert get_wish_list(db, "jones", "alice") == ["Book"]
    assert get_wish_list(db, "smith", "bob") == ["Tea"]
    assert get_wish_list(db, "jones", "bob") == []
    assert len(db.table(WISHES_TABLE)) == 3


def test_migration_does_not_overwrite_existing_group_list(db, config):
    db.table(WISHES_TABLE).insert({"username": "alice", "items": ["Book"]})
    save_wish_list(db, "jones", "alice", ["Scarf"])

    migrate_legacy_wishes(db, config)

    assert get_wish_list(db, "smith", "alice") == ["Book"]
    assert get_wish_list(db, "jones", "alice") == ["Scarf"]


def test_migration_keeps_lists_of_users_not_in_any_group(db, config):
    db.table(WISHES_TABLE).insert({"username": "ghost", "items": ["Chain"]})

    assert migrate_legacy_wishes(db, config) == 0
    assert len(db.table(WISHES_TABLE)) == 1


def test_migration_is_idempotent(db, config):
    db.table(WISHES_TABLE).insert({"username": "alice", "items": ["Book"]})

    assert migrate_legacy_wishes(db, config) == 1
    assert migrate_legacy_wishes(db, config) == 0
    assert len(db.table(WISHES_TABLE)) == 2
