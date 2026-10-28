"""Committee membership records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CommitteeMemberRecord:
    """One person who belongs to the building committee."""

    user_id: str
    full_name: str
    email: str


class UnknownCommitteeUser(Exception):
    """Raised when the chosen user does not exist."""


class DuplicateCommitteeMember(Exception):
    """Raised when the user is already on the committee."""


class CommitteeMemberNotFound(Exception):
    """Raised when removing a user who is not on the committee."""
