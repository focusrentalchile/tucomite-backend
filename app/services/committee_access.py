"""Resolves whether a person may act with committee powers."""

from sqlalchemy.orm import Session

from app.repositories.committee_repository import SqlCommitteeRepository

# Role keys that may manage topics without a separate membership row.
# The building owner (client) is never a committee seat.
COMMITTEE_CAPABLE_ROLES = frozenset({"committee"})

# Catalog keys that unlock committee-style topic work for custom roles.
COMMITTEE_PERMISSIONS = frozenset({"matters.create", "matters.comment", "agreements.vote"})


def ensure_committee_access(
    db: Session,
    user_id: str,
    role_name: str,
    permissions: frozenset[str] | None = None,
) -> bool:
    """Return True when the person may act with committee powers.

    Holders of the committee role are stored as members automatically.
    The client (building owner) may use the same APIs but is never enrolled
    as a committee member and does not count as a voter seat.
    Custom roles with matters/vote permissions also qualify; writers are enrolled.
    """
    key = role_name.casefold().strip()
    repo = SqlCommitteeRepository(db)
    held = permissions or frozenset()
    if key == "client":
        # Building owner may use committee APIs but is never a voter seat.
        if repo.get_member(user_id) is not None:
            repo.remove_member(user_id)
        return True
    if key == "committee" or "matters.create" in held or "agreements.vote" in held:
        if repo.get_member(user_id) is None:
            repo.add_member(user_id)
        return True
    if key in COMMITTEE_CAPABLE_ROLES:
        return True
    if held & COMMITTEE_PERMISSIONS:
        return True
    return repo.get_member(user_id) is not None


def is_listed_committee_member(db: Session, user_id: str) -> bool:
    """True only when the person sits on the committee_members table."""
    return SqlCommitteeRepository(db).get_member(user_id) is not None
