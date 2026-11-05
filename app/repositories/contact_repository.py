"""MySQL repository for public contact messages."""

from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contact import ContactMessageRecord
from app.models.contact import ContactMessageModel


def _stamp(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value is not None else None


class ContactRepository(Protocol):
    """Persistence port for contact messages."""

    def list_messages(self) -> list[ContactMessageRecord]:
        """Return every message, newest first."""

    def add_message(self, message: ContactMessageRecord) -> None:
        """Insert a contact message."""


class SqlContactRepository:
    """SQLAlchemy adapter for contact_messages."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_messages(self) -> list[ContactMessageRecord]:
        rows = self._session.scalars(
            select(ContactMessageModel).order_by(ContactMessageModel.created_at.desc()),
        ).all()
        return [self._message(row) for row in rows]

    def add_message(self, message: ContactMessageRecord) -> None:
        self._session.add(
            ContactMessageModel(
                id=message.id,
                name=message.name,
                email=message.email,
                message=message.message,
                privacy_accepted=message.privacy_accepted,
                privacy_accepted_at=(
                    datetime.fromisoformat(message.privacy_accepted_at)
                    if message.privacy_accepted_at
                    else None
                ),
                created_at=datetime.fromisoformat(message.created_at),
            ),
        )
        self._session.flush()

    def _message(self, row: ContactMessageModel) -> ContactMessageRecord:
        return ContactMessageRecord(
            id=row.id,
            name=row.name,
            email=row.email,
            message=row.message,
            privacy_accepted=bool(row.privacy_accepted),
            privacy_accepted_at=_stamp(row.privacy_accepted_at),
            created_at=_stamp(row.created_at) or "",
        )
