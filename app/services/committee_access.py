"""Resolves whether a person may act with committee powers."""

from sqlalchemy.orm import Session

from app.repositories.committee_repository import SqlCommitteeRepository

# Role keys that may manage topics and projects without a separate membership row.
COMMITTEE_CAPABLE_ROLES = frozenset({"committee", "client"})

# Catalog keys that unlock committee-style topic work for custom roles.
COMMITTEE_PERMISSIONS = frozenset({"matters.create", "matters.comment", "agreements.vote"})


def ensure_committee_access(
    db: Session,
    user_id: str,
    role_name: str,
    permissions: frozenset[str] | None = None,
) -> bool:
    """Return True when the person may act as committee.

    Holders of the committee role are stored as members automatically.
    The client role can do the same work without joining the members table.
    Custom roles with matters/vote permissions also qualify; writers are enrolled.
    """
    key = role_name.casefold().strip()
    repo = SqlCommitteeRepository(db)
    held = permissions or frozenset()
    if key == "committee" or "matters.create" in held or "agreements.vote" in held:
        if repo.get_member(user_id) is None:
            repo.add_member(user_id)
        return True
    if key in COMMITTEE_CAPABLE_ROLES:
        return True
    if held & COMMITTEE_PERMISSIONS:
        return True
    return repo.get_member(user_id) is not None
