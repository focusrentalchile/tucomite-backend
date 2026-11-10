"""Persistence for account closure requests."""

from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.account import AccountClosureRequestRecord
from app.models.account import AccountClosureRequestModel


class AccountClosureRepository(Protocol):
    """Persistence port used by the account service."""

    def add(self, record: AccountClosureRequestRecord) -> None:
        """Insert one closure request."""

    def list_for_user(self, user_id: str) -> list[AccountClosureRequestRecord]:
        """Return the closure requests of one user, newest first."""


class SqlAccountClosureRepository:
    """SQLAlchemy adapter for account_closure_requests."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: AccountClosureRequestRecord) -> None:
        created = datetime.fromisoformat(record.created_at.replace("Z", "+00:00"))
        if created.tzinfo is not None:
            created = created.astimezone(timezone.utc).replace(tzinfo=None)
        self._session.add(
            AccountClosureRequestModel(
                id=record.id,
                user_id=record.user_id,
                client_id=record.client_id,
                reason=record.reason,
                created_at=created,
            ),
        )
        self._session.flush()

    def list_for_user(self, user_id: str) -> list[AccountClosureRequestRecord]:
        rows = self._session.scalars(
            select(AccountClosureRequestModel)
            .where(AccountClosureRequestModel.user_id == user_id)
            .order_by(AccountClosureRequestModel.created_at.desc()),
        ).all()
        return [
            AccountClosureRequestRecord(
                id=row.id,
                user_id=row.user_id,
                client_id=row.client_id,
                reason=row.reason,
                created_at=row.created_at.replace(tzinfo=timezone.utc).isoformat(),
            )
            for row in rows
        ]
