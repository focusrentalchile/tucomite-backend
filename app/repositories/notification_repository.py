"""Persistence for in-app notifications."""

from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.notifications import NotificationRecord
from app.models.notifications import NotificationModel


class NotificationRepository(Protocol):
    """Persistence port for notifications."""

    def list_for_user(self, user_id: str, *, unread_only: bool = False) -> list[NotificationRecord]:
        """Return notices for one user, newest first."""

    def add(self, record: NotificationRecord) -> None:
        """Insert one notice."""

    def mark_read(self, notification_id: str, user_id: str) -> NotificationRecord | None:
        """Mark one notice as read when it belongs to the user."""


class SqlNotificationRepository:
    """SQLAlchemy adapter for notifications."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: str, *, unread_only: bool = False) -> list[NotificationRecord]:
        query = select(NotificationModel).where(NotificationModel.user_id == user_id)
        if unread_only:
            query = query.where(NotificationModel.read_at.is_(None))
        rows = self._session.execute(
            query.order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc()),
        ).scalars().all()
        return [self._record(row) for row in rows]

    def add(self, record: NotificationRecord) -> None:
        self._session.add(
            NotificationModel(
                id=record.id,
                user_id=record.user_id,
                kind=record.kind,
                title=record.title,
                body=record.body,
            ),
        )
        self._session.flush()

    def mark_read(self, notification_id: str, user_id: str) -> NotificationRecord | None:
        row = self._session.get(NotificationModel, notification_id)
        if row is None or row.user_id != user_id:
            return None
        if row.read_at is None:
            row.read_at = datetime.now(timezone.utc)
            self._session.flush()
        return self._record(row)

    def _record(self, row: NotificationModel) -> NotificationRecord:
        return NotificationRecord(
            id=row.id,
            user_id=row.user_id,
            kind=row.kind,
            title=row.title,
            body=row.body,
            created_at=row.created_at.isoformat() if row.created_at else "",
            read_at=row.read_at.isoformat() if row.read_at else None,
        )
