"""Secret Santa draws.

Each group has at most one draw, run by the admin. A draw is stored as a single
document, so it is either saved completely or not at all.
"""

import random
from datetime import datetime, timezone
from typing import Dict, List, Optional

from tinydb import Query, TinyDB

DRAWS_TABLE = "draws"
LEGACY_TABLE_PREFIX = "assignments_"


def generate_assignments(
    participants: List[str],
    exclusions: Dict[str, List[str]],
    max_attempts: int = 1000,
) -> Dict[str, str]:
    """Generate Secret Santa assignments ensuring no self-assignments and respecting exclusions

    Args:
        participants: List of participant usernames
        exclusions: Dict mapping username to list of usernames they cannot be assigned to

    Raises:
        ValueError: If no valid assignment was found
    """
    givers = participants.copy()
    receivers = participants.copy()

    for _ in range(max_attempts):
        random.shuffle(receivers)
        if all(
            giver != receiver and receiver not in exclusions.get(giver, [])
            for giver, receiver in zip(givers, receivers)
        ):
            return dict(zip(givers, receivers))

    raise ValueError(
        f"Could not generate valid assignments after {max_attempts} attempts. "
        "Check if constraints are too restrictive."
    )


def _family_query(family_id: str):
    return Query().family_id == family_id


def get_draw(db: TinyDB, family_id: str) -> Optional[Dict]:
    """Get the draw of a group, or None if it has not been run yet

    The draw is a dict with "family_id", "drawn_at" (ISO timestamp, None for
    draws migrated from older versions) and "assignments" (giver -> receiver).
    """
    return db.table(DRAWS_TABLE).get(_family_query(family_id))


def run_draw(db: TinyDB, family: Dict) -> Dict:
    """Run the draw for a group, replacing any previous draw

    Raises:
        ValueError: If the exclusions make a valid draw impossible
    """
    usernames = [p["username"] for p in family["participants"]]
    if len(usernames) < 2:
        raise ValueError("A draw needs at least 2 participants.")
    exclusions = {p["username"]: p.get("exclude", []) for p in family["participants"]}

    draw = {
        "family_id": family["id"],
        "drawn_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "assignments": generate_assignments(usernames, exclusions),
    }
    db.table(DRAWS_TABLE).upsert(draw, _family_query(family["id"]))
    return draw


def participants_changed(draw: Dict, family: Dict) -> bool:
    """Check whether participants were added to or removed from the group since the draw"""
    return set(draw["assignments"]) != {p["username"] for p in family["participants"]}


def migrate_legacy_assignments(db: TinyDB) -> int:
    """Convert the per-group "assignments_<family_id>" tables created by older
    versions of the app into draws.

    Returns:
        Number of groups migrated
    """
    draws_table = db.table(DRAWS_TABLE)
    migrated = 0

    for table_name in db.tables():
        if not table_name.startswith(LEGACY_TABLE_PREFIX):
            continue

        family_id = table_name[len(LEGACY_TABLE_PREFIX) :]
        records = db.table(table_name).all()
        if records and not draws_table.contains(_family_query(family_id)):
            draws_table.insert(
                {
                    "family_id": family_id,
                    "drawn_at": None,
                    "assignments": {r["giver"]: r["receiver"] for r in records},
                }
            )
            migrated += 1

        db.drop_table(table_name)

    return migrated
