"""Persistence for committee members."""

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.committee import CommitteeMemberRecord
from app.models.access import UserModel
from app.models.committee import CommitteeMemberModel


class CommitteeRepository(Protocol):
    """Persistence port used by the committee service."""

    def list_members(self) -> list[CommitteeMemberRecord]:
        """Return every committee member ordered by name."""

    def get_member(self, user_id: str) -> CommitteeMemberRecord | None:
        """Return one committee member when present."""

    def add_member(self, user_id: str) -> None:
        """Insert one committee membership."""

    def remove_member(self, user_id: str) -> None:
        """Delete one committee membership."""

    def get_user_profile(self, user_id: str) -> CommitteeMemberRecord | None:
        """Return name and email for a user id."""


class SqlCommitteeRepository:
    """SQLAlchemy adapter for the committee_members table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_members(self) -> list[CommitteeMemberRecord]:
        rows = self._session.execute(
            select(UserModel)
            .join(CommitteeMemberModel, CommitteeMemberModel.user_id == UserModel.id)
            .order_by(UserModel.full_name),
        ).scalars().all()
        return [self._member(row) for row in rows]

    def get_member(self, user_id: str) -> CommitteeMemberRecord | None:
        row = self._session.get(CommitteeMemberModel, user_id)
        if row is None:
            return None
        return self.get_user_profile(user_id)

    def add_member(self, user_id: str) -> None:
        self._session.add(CommitteeMemberModel(user_id=user_id))

    def remove_member(self, user_id: str) -> None:
        row = self._session.get(CommitteeMemberModel, user_id)
        if row is not None:
            self._session.delete(row)

    def get_user_profile(self, user_id: str) -> CommitteeMemberRecord | None:
        row = self._session.get(UserModel, user_id)
        if row is None:
            return None
        return self._member(row)

    def _member(self, row: UserModel) -> CommitteeMemberRecord:
        return CommitteeMemberRecord(user_id=row.id, full_name=row.full_name, email=row.email)
