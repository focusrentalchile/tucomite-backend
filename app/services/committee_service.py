"""Manages who belongs to the building committee."""

from app.domain.committee import (
    CommitteeMemberNotFound,
    CommitteeMemberRecord,
    DuplicateCommitteeMember,
    UnknownCommitteeUser,
)
from app.repositories.committee_repository import CommitteeRepository


class CommitteeService:
    """Adds and removes committee members stored in MySQL."""

    def __init__(self, repository: CommitteeRepository) -> None:
        self._repository = repository

    def list_members(self) -> list[CommitteeMemberRecord]:
        """Return every committee member."""
        return self._repository.list_members()

    def add_member(self, user_id: str) -> CommitteeMemberRecord:
        """Add one existing user to the committee."""
        profile = self._repository.get_user_profile(user_id)
        if profile is None:
            raise UnknownCommitteeUser()
        if self._repository.get_member(user_id) is not None:
            raise DuplicateCommitteeMember()
        self._repository.add_member(user_id)
        return profile

    def remove_member(self, user_id: str) -> None:
        """Remove one user from the committee."""
        if self._repository.get_member(user_id) is None:
            raise CommitteeMemberNotFound()
        self._repository.remove_member(user_id)
