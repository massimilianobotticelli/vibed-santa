"""Wish list storage.

Wish lists are scoped per group: a person who participates in more than one
group keeps a separate wish list for each, and only their Secret Santa in that
group can see it.
"""

from typing import Dict, List

from tinydb import Query, TinyDB

WISHES_TABLE = "wishes"


def _wish_query(family_id: str, username: str):
    Wish = Query()
    return (Wish.family_id == family_id) & (Wish.username == username)


def get_wish_list(db: TinyDB, family_id: str, username: str) -> List[str]:
    """Get the wish list of a user within a specific group"""
    result = db.table(WISHES_TABLE).get(_wish_query(family_id, username))
    return result["items"] if result else []


def save_wish_list(db: TinyDB, family_id: str, username: str, items: List[str]):
    """Save the wish list of a user within a specific group"""
    db.table(WISHES_TABLE).upsert(
        {"family_id": family_id, "username": username, "items": items},
        _wish_query(family_id, username),
    )


def migrate_legacy_wishes(db: TinyDB, config: Dict) -> int:
    """Assign group-less wish lists (stored before lists were scoped per group)
    to every group the user currently belongs to.

    A legacy list is not copied over a list the user already has in a group.
    Legacy lists of users that are in no group are kept untouched, so they can
    still be migrated if the user is added back to the config.

    Returns:
        Number of legacy wish lists migrated
    """
    wishes_table = db.table(WISHES_TABLE)
    Wish = Query()
    migrated = 0

    for record in wishes_table.search(~Wish.family_id.exists()):
        username = record["username"]
        family_ids = [
            family["id"]
            for family in config.get("families", [])
            if any(p["username"] == username for p in family.get("participants", []))
        ]
        if not family_ids:
            continue

        for family_id in family_ids:
            if not wishes_table.contains(_wish_query(family_id, username)):
                save_wish_list(db, family_id, username, record["items"])

        wishes_table.remove(doc_ids=[record.doc_id])
        migrated += 1

    return migrated
