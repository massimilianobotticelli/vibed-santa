import pytest
from tinydb import TinyDB

from draws import (
    DRAWS_TABLE,
    generate_assignments,
    get_draw,
    migrate_legacy_assignments,
    participants_changed,
    run_draw,
)


@pytest.fixture
def db(tmp_path):
    db = TinyDB(tmp_path / "secret_santa.db")
    yield db
    db.close()


@pytest.fixture
def family():
    return {
        "id": "smith",
        "participants": [
            {"username": "alice", "exclude": ["bob"]},
            {"username": "bob", "exclude": ["alice"]},
            {"username": "dave"},
            {"username": "erin"},
        ],
    }


@pytest.mark.parametrize("attempt", range(50))
def test_assignments_form_a_valid_secret_santa(attempt):
    participants = ["alice", "bob", "dave", "erin"]
    exclusions = {"alice": ["bob"], "bob": ["alice"]}

    assignments = generate_assignments(participants, exclusions)

    assert sorted(assignments) == sorted(participants)
    assert sorted(assignments.values()) == sorted(participants)
    for giver, receiver in assignments.items():
        assert giver != receiver
        assert receiver not in exclusions.get(giver, [])


def test_impossible_constraints_raise():
    with pytest.raises(ValueError):
        generate_assignments(["alice", "bob"], {"alice": ["bob"]})


def test_no_draw_before_admin_runs_it(db):
    assert get_draw(db, "smith") is None


def test_run_draw_stores_the_draw(db, family):
    draw = run_draw(db, family)

    assert get_draw(db, "smith") == draw
    assert draw["drawn_at"] is not None
    assert set(draw["assignments"]) == {"alice", "bob", "dave", "erin"}


def test_redoing_the_draw_replaces_the_previous_one(db, family):
    run_draw(db, family)
    run_draw(db, family)

    assert len(db.table(DRAWS_TABLE)) == 1


def test_draws_are_separate_per_group(db, family):
    other = {"id": "jones", "participants": [{"username": "a"}, {"username": "b"}]}
    run_draw(db, family)
    run_draw(db, other)

    assert get_draw(db, "jones")["assignments"] == {"a": "b", "b": "a"}
    assert set(get_draw(db, "smith")["assignments"]) == {
        "alice",
        "bob",
        "dave",
        "erin",
    }


def test_participants_changed(db, family):
    draw = run_draw(db, family)
    assert not participants_changed(draw, family)

    family["participants"].append({"username": "new"})
    assert participants_changed(draw, family)

    family["participants"] = family["participants"][1:-1]
    assert participants_changed(draw, family)


def test_legacy_assignment_tables_become_draws(db):
    db.table("assignments_smith").insert_multiple(
        [{"giver": "alice", "receiver": "bob"}, {"giver": "bob", "receiver": "alice"}]
    )

    assert migrate_legacy_assignments(db) == 1

    draw = get_draw(db, "smith")
    assert draw["assignments"] == {"alice": "bob", "bob": "alice"}
    assert draw["drawn_at"] is None
    assert "assignments_smith" not in db.tables()
    assert migrate_legacy_assignments(db) == 0


def test_legacy_migration_keeps_existing_draw(db, family):
    draw = run_draw(db, family)
    db.table("assignments_smith").insert({"giver": "x", "receiver": "y"})

    migrate_legacy_assignments(db)

    assert get_draw(db, "smith") == draw
