"""Resolves whether a person may act with committee powers."""

from sqlalchemy.orm import Session

from app.repositories.committee_repository import SqlCommitteeRepository

# Role keys that may manage topics and projects without a separate membership row.
COMMITTEE_CAPABLE_ROLES = frozenset({"committee", "client"})


def ensure_committee_access(db: Session, user_id: str, role_name: str) -> bool:
    """Return True when the person may act as committee.

    Holders of the committee role are stored as members automatically.
    The client role can do the same work without joining the members table.
    """
    key = role_name.casefold().strip()
    repo = SqlCommitteeRepository(db)
    if key == "committee":
        if repo.get_member(user_id) is None:
            repo.add_member(user_id)
        return True
    if key in COMMITTEE_CAPABLE_ROLES:
        return True
    return repo.get_member(user_id) is not None
