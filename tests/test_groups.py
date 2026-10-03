import re

import pytest
from tinydb import TinyDB

import groups
from draws import get_draw, run_draw
from wishes import get_wish_list, save_wish_list


@pytest.fixture
def db(tmp_path):
    db = TinyDB(tmp_path / "secret_santa.db")
    yield db
    db.close()


def family(config, family_id):
    return next(f for f in config["families"] if f["id"] == family_id)


def test_generated_passwords_are_readable_and_random():
    passwords = {groups.generate_password() for _ in range(100)}

    assert len(passwords) == 100
    for password in passwords:
        assert re.fullmatch(r"[a-z2-9]{4}-[a-z2-9]{4}", password)
        assert not set(password) & set("lo01i")


def test_add_person_derives_username_and_generates_password(db):
    person = groups.add_person(db, "Alice Smith")

    assert person["username"] == "alice.smith"
    assert len(person["password"]) == 9
    assert groups.get_person(db, "alice.smith") == person


def test_derived_usernames_are_unique_and_ascii(db):
    first = groups.add_person(db, "Papà")
    second = groups.add_person(db, "Papa")

    assert first["username"] == "papa"
    assert second["username"] == "papa2"


def test_add_person_with_explicit_credentials(db):
    person = groups.add_person(db, "Bob", username="bob", password="secret")

    assert (person["username"], person["password"]) == ("bob", "secret")
    with pytest.raises(ValueError):
        groups.add_person(db, "Another Bob", username="bob")


def test_authenticate(db):
    groups.add_person(db, "Bob", username="bob", password="secret")

    assert groups.authenticate(db, "bob", "secret")["name"] == "Bob"
    assert groups.authenticate(db, " bob ", "secret")["username"] == "bob"
    assert groups.authenticate(db, "bob", "wrong") is None
    assert groups.authenticate(db, "nobody", "secret") is None


def test_authenticate_with_non_ascii_password(db):
    groups.add_person(db, "Jürgen", username="juergen", password="grüße")

    assert groups.authenticate(db, "juergen", "grüße")
    assert groups.authenticate(db, "juergen", "grusse") is None


def test_update_person(db):
    groups.add_person(db, "Bob", username="bob", password="old")

    groups.update_person(db, "bob", name="Bob Smith", password="new")

    person = groups.get_person(db, "bob")
    assert (person["name"], person["password"]) == ("Bob Smith", "new")


def test_exclusions_apply_in_both_directions(db):
    for name in ("alice", "bob", "dave"):
        groups.add_person(db, name, username=name)

    groups.set_exclusions(db, "alice", ["bob"])
    assert groups.get_person(db, "alice")["exclude"] == ["bob"]
    assert groups.get_person(db, "bob")["exclude"] == ["alice"]

    groups.set_exclusions(db, "alice", ["dave"])
    assert groups.get_person(db, "alice")["exclude"] == ["dave"]
    assert groups.get_person(db, "bob")["exclude"] == []
    assert groups.get_person(db, "dave")["exclude"] == ["alice"]


def test_group_ids_are_derived_from_the_name_and_unique(db):
    first = groups.add_group(db, "Smith Family", 30, "€", [])
    second = groups.add_group(db, "Smith Family", 30, "€", [])

    assert first["id"] == "smith_family"
    assert second["id"] == "smith_family2"


def test_whole_budgets_are_stored_as_int(db):
    assert groups.add_group(db, "A", 30.0, "€", [])["budget"] == 30
    assert groups.add_group(db, "B", 12.5, "€", [])["budget"] == 12.5


def test_person_in_several_groups(db):
    for name in ("alice", "bob", "carol"):
        groups.add_person(db, name, username=name)
    groups.add_group(db, "Smith", 30, "€", ["alice", "bob"])
    groups.add_group(db, "Jones", 50, "€", ["carol"])

    groups.set_person_groups(db, "alice", ["smith", "jones"])
    assert groups.get_group(db, "jones")["members"] == ["carol", "alice"]

    groups.set_person_groups(db, "alice", ["jones"])
    assert groups.get_group(db, "smith")["members"] == ["bob"]
    assert groups.get_group(db, "jones")["members"] == ["carol", "alice"]


def test_update_group(db):
    groups.add_person(db, "alice", username="alice")
    group = groups.add_group(db, "Smith", 30, "€", [])

    groups.update_group(db, group["id"], "The Smiths", 40, "$", ["alice"])

    assert groups.get_group(db, group["id"]) == {
        "id": "smith",
        "name": "The Smiths",
        "budget": 40,
        "currency": "$",
        "members": ["alice"],
    }


def test_build_config_has_the_structure_of_the_yaml_config(db):
    for name in ("alice", "bob", "dave"):
        groups.add_person(db, name.title(), username=name, password="pw")
    groups.set_exclusions(db, "alice", ["bob"])
    groups.add_group(db, "Smith", 30, "€", ["alice", "dave"])

    assert groups.build_config(db) == {
        "families": [
            {
                "id": "smith",
                "name": "Smith",
                "budget": 30,
                "currency": "€",
                "participants": [
                    # bob is not in the group, so the exclusion is irrelevant
                    {"username": "alice", "name": "Alice", "password": "pw", "exclude": []},
                    {"username": "dave", "name": "Dave", "password": "pw", "exclude": []},
                ],
            }
        ]
    }


def test_delete_person_cleans_up_everywhere(db):
    for name in ("alice", "bob"):
        groups.add_person(db, name, username=name)
    groups.set_exclusions(db, "alice", ["bob"])
    groups.add_group(db, "Smith", 30, "€", ["alice", "bob"])
    save_wish_list(db, "smith", "alice", ["Book"])

    groups.delete_person(db, "alice")

    assert groups.get_person(db, "alice") is None
    assert groups.get_person(db, "bob")["exclude"] == []
    assert groups.get_group(db, "smith")["members"] == ["bob"]
    assert get_wish_list(db, "smith", "alice") == []


def test_delete_group_deletes_its_draw_and_wishes_but_not_people(db):
    for name in ("alice", "bob"):
        groups.add_person(db, name, username=name)
    groups.add_group(db, "Smith", 30, "€", ["alice", "bob"])
    groups.add_group(db, "Jones", 30, "€", ["alice", "bob"])
    config = groups.build_config(db)
    run_draw(db, family(config, "smith"))
    run_draw(db, family(config, "jones"))
    save_wish_list(db, "smith", "alice", ["Book"])
    save_wish_list(db, "jones", "alice", ["Scarf"])

    groups.delete_group(db, "smith")

    assert groups.get_group(db, "smith") is None
    assert get_draw(db, "smith") is None
    assert get_wish_list(db, "smith", "alice") == []
    assert get_draw(db, "jones") is not None
    assert get_wish_list(db, "jones", "alice") == ["Scarf"]
    assert groups.get_person(db, "alice") is not None


LEGACY_CONFIG = {
    "families": [
        {
            "id": "smith",
            "name": "Smith",
            "budget": 30,
            "currency": "€",
            "participants": [
                {"username": "alice", "password": "a", "name": "Alice", "exclude": ["bob"]},
                {"username": "bob", "password": "b", "name": "Bob"},
            ],
        },
        {
            "id": "jones",
            "name": "Jones",
            "budget": 50,
            "currency": "€",
            "participants": [
                {"username": "alice", "password": "a", "name": "Alice", "exclude": []},
                {"username": "carol", "password": 1234, "name": "Carol"},
            ],
        },
    ]
}


def test_import_legacy_config(db):
    assert groups.import_config(db, LEGACY_CONFIG)

    config = groups.build_config(db)
    assert [f["id"] for f in config["families"]] == ["jones", "smith"]
    assert [p["username"] for p in family(config, "jones")["participants"]] == [
        "alice",
        "carol",
    ]
    assert groups.get_person(db, "alice")["exclude"] == ["bob"]
    # YAML may parse numeric passwords as int
    assert groups.get_person(db, "carol")["password"] == "1234"


def test_import_only_into_an_empty_database(db):
    groups.add_person(db, "Someone")

    assert not groups.import_config(db, LEGACY_CONFIG)
    assert groups.list_groups(db) == []
