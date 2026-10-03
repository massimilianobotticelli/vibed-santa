"""Groups and people, managed by the admin.

A person has a single login (username and password) and can be a member of
several groups. Exclusions ("doesn't exchange gifts with") are stored on the
person and apply in every group.

Passwords of people are stored in plain text on purpose: the admin needs to be
able to see them in order to share them.
"""

import hmac
import re
import secrets
import unicodedata
from typing import Dict, Iterable, List, Optional

from tinydb import Query, TinyDB

from draws import DRAWS_TABLE
from wishes import WISHES_TABLE

PEOPLE_TABLE = "people"
GROUPS_TABLE = "groups"

# No look-alike characters (l/1, o/0) so passwords are easy to read out loud
_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def generate_password() -> str:
    """Generate a password that is easy to read and type, like "k7mp-x3qa" """
    chars = [secrets.choice(_PASSWORD_ALPHABET) for _ in range(8)]
    return "".join(chars[:4]) + "-" + "".join(chars[4:])


def _slugify(text: str, separator: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", separator, ascii_text.lower()).strip(separator)


def _unique(base: str, existing: Iterable[str]) -> str:
    existing = set(existing)
    candidate, n = base, 2
    while candidate in existing:
        candidate = f"{base}{n}"
        n += 1
    return candidate


def _normalize_budget(budget: float):
    """Store whole budgets as int, so they are shown as "€30" and not "€30.0" """
    return int(budget) if float(budget).is_integer() else budget


# People
def _person_query(username: str):
    return Query().username == username


def list_people(db: TinyDB) -> List[Dict]:
    """All people, sorted by name"""
    return sorted(db.table(PEOPLE_TABLE).all(), key=lambda p: p["name"].lower())


def get_person(db: TinyDB, username: str) -> Optional[Dict]:
    return db.table(PEOPLE_TABLE).get(_person_query(username))


def add_person(
    db: TinyDB,
    name: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict:
    """Add a person; the username is derived from the name and the password
    generated when not given

    Raises:
        ValueError: If the username already exists
    """
    taken = (p["username"] for p in db.table(PEOPLE_TABLE).all())
    username = (username or "").strip() or _unique(_slugify(name, ".") or "user", taken)
    if get_person(db, username):
        raise ValueError(f"Username '{username}' already exists")

    person = {
        "username": username,
        "name": name.strip(),
        "password": (password or "").strip() or generate_password(),
        "exclude": [],
    }
    db.table(PEOPLE_TABLE).insert(person)
    return person


def authenticate(db: TinyDB, username: str, password: str) -> Optional[Dict]:
    """Check the login of a person

    Returns:
        The person, or None if the username or the password is wrong
    """
    person = get_person(db, username.strip())
    if person and hmac.compare_digest(
        person["password"].encode("utf-8"), password.encode("utf-8")
    ):
        return person
    return None


def update_person(
    db: TinyDB, username: str, name: Optional[str] = None, password: Optional[str] = None
):
    """Change the name and/or the password of a person"""
    fields = {}
    if name is not None:
        fields["name"] = name.strip()
    if password is not None:
        fields["password"] = password.strip()
    db.table(PEOPLE_TABLE).update(fields, _person_query(username))


def set_exclusions(db: TinyDB, username: str, excluded: Iterable[str]):
    """Set who a person doesn't exchange gifts with, in both directions"""
    people_table = db.table(PEOPLE_TABLE)
    excluded = set(excluded) - {username}

    for person in people_table.all():
        other = person["username"]
        if other == username:
            new = excluded
        elif other in excluded:
            new = set(person.get("exclude", [])) | {username}
        else:
            new = set(person.get("exclude", [])) - {username}

        if new != set(person.get("exclude", [])):
            people_table.update({"exclude": sorted(new)}, _person_query(other))


def set_person_groups(db: TinyDB, username: str, group_ids: Iterable[str]):
    """Make a person a member of exactly the given groups"""
    group_ids = set(group_ids)
    for group in list_groups(db):
        members = group["members"]
        if group["id"] in group_ids and username not in members:
            members = members + [username]
        elif group["id"] not in group_ids and username in members:
            members = [m for m in members if m != username]
        else:
            continue
        db.table(GROUPS_TABLE).update({"members": members}, _group_query(group["id"]))


def delete_person(db: TinyDB, username: str):
    """Delete a person, removing them from all groups, exclusions and wish lists"""
    set_exclusions(db, username, [])
    set_person_groups(db, username, [])
    db.table(WISHES_TABLE).remove(Query().username == username)
    db.table(PEOPLE_TABLE).remove(_person_query(username))


# Groups
def _group_query(group_id: str):
    return Query().id == group_id


def list_groups(db: TinyDB) -> List[Dict]:
    """All groups, sorted by name"""
    return sorted(db.table(GROUPS_TABLE).all(), key=lambda g: g["name"].lower())


def get_group(db: TinyDB, group_id: str) -> Optional[Dict]:
    return db.table(GROUPS_TABLE).get(_group_query(group_id))


def add_group(
    db: TinyDB, name: str, budget: float, currency: str, members: Iterable[str]
) -> Dict:
    """Create a group; its ID is derived from the name and never changes"""
    taken = (g["id"] for g in db.table(GROUPS_TABLE).all())
    group = {
        "id": _unique(_slugify(name, "_") or "group", taken),
        "name": name.strip(),
        "budget": _normalize_budget(budget),
        "currency": currency.strip(),
        "members": list(members),
    }
    db.table(GROUPS_TABLE).insert(group)
    return group


def update_group(
    db: TinyDB,
    group_id: str,
    name: str,
    budget: float,
    currency: str,
    members: Iterable[str],
):
    db.table(GROUPS_TABLE).update(
        {
            "name": name.strip(),
            "budget": _normalize_budget(budget),
            "currency": currency.strip(),
            "members": list(members),
        },
        _group_query(group_id),
    )


def delete_group(db: TinyDB, group_id: str):
    """Delete a group together with its draw and its wish lists"""
    db.table(DRAWS_TABLE).remove(Query().family_id == group_id)
    db.table(WISHES_TABLE).remove(Query().family_id == group_id)
    db.table(GROUPS_TABLE).remove(_group_query(group_id))


# Config
def build_config(db: TinyDB) -> Dict:
    """Build the groups in the same structure as the YAML configuration of
    older versions ({"families": [{"id", "name", "budget", "currency",
    "participants": [{"username", "name", "password", "exclude"}]}]})
    """
    people = {p["username"]: p for p in db.table(PEOPLE_TABLE).all()}
    families = []

    for group in list_groups(db):
        members = [m for m in group["members"] if m in people]
        participants = [
            {
                "username": username,
                "name": people[username]["name"],
                "password": people[username]["password"],
                "exclude": [e for e in people[username]["exclude"] if e in members],
            }
            for username in members
        ]
        families.append(
            {
                "id": group["id"],
                "name": group["name"],
                "budget": group["budget"],
                "currency": group["currency"],
                "participants": sorted(participants, key=lambda p: p["name"].lower()),
            }
        )

    return {"families": families}


def import_config(db: TinyDB, config: Dict) -> bool:
    """Import groups and people from a YAML configuration of older versions

    The import only happens into an empty database (no groups and no people),
    so it can never overwrite changes made in the admin console. Group IDs and
    usernames are kept, so existing draws and wish lists stay valid.

    Returns:
        True if the configuration was imported
    """
    if len(db.table(GROUPS_TABLE)) or len(db.table(PEOPLE_TABLE)):
        return False

    people = {}
    for family in config.get("families", []):
        for participant in family.get("participants", []):
            # A person in several groups keeps the password of the first group
            person = people.setdefault(
                participant["username"],
                {
                    "username": participant["username"],
                    "name": participant["name"],
                    "password": str(participant["password"]),
                    "exclude": [],
                },
            )
            person["exclude"] = sorted(
                set(person["exclude"]) | set(participant.get("exclude") or [])
            )

    db.table(PEOPLE_TABLE).insert_multiple(people.values())
    db.table(GROUPS_TABLE).insert_multiple(
        {
            "id": family["id"],
            "name": family["name"],
            "budget": family.get("budget", 0),
            "currency": family.get("currency", "$"),
            "members": [p["username"] for p in family.get("participants", [])],
        }
        for family in config.get("families", [])
    )
    return True
