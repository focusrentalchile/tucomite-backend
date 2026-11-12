"""Persistence for invitations."""

from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.invitations import InvitationRecord
from app.models.invitations import InvitationModel


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
    return value.isoformat(timespec="seconds")


class InvitationRepository(Protocol):
    """Port used by InvitationService."""

    def list_all(self) -> list[InvitationRecord]: ...

    def list_for_client(self, client_id: str) -> list[InvitationRecord]: ...

    def get(self, invitation_id: str) -> InvitationRecord | None: ...

    def get_by_token(self, token: str) -> InvitationRecord | None: ...

    def get_by_email(self, email: str) -> InvitationRecord | None: ...

    def add(self, record: InvitationRecord) -> None: ...

    def save(self, record: InvitationRecord) -> None: ...

    def delete(self, invitation_id: str) -> None: ...


class SqlInvitationRepository:
    """SQLAlchemy adapter for invitations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[InvitationRecord]:
        rows = self._session.scalars(
            select(InvitationModel).order_by(InvitationModel.created_at.desc()),
        ).all()
        return [self._to_record(row) for row in rows]

    def list_for_client(self, client_id: str) -> list[InvitationRecord]:
        rows = self._session.scalars(
            select(InvitationModel)
            .where(InvitationModel.client_id == client_id)
            .order_by(InvitationModel.created_at.desc()),
        ).all()
        return [self._to_record(row) for row in rows]

    def get(self, invitation_id: str) -> InvitationRecord | None:
        row = self._session.get(InvitationModel, invitation_id)
        return self._to_record(row) if row else None

    def get_by_token(self, token: str) -> InvitationRecord | None:
        row = self._session.scalars(
            select(InvitationModel).where(InvitationModel.token == token),
        ).first()
        return self._to_record(row) if row else None

    def get_by_email(self, email: str) -> InvitationRecord | None:
        cleaned = email.strip().lower()
        row = self._session.scalars(
            select(InvitationModel).where(InvitationModel.email == cleaned),
        ).first()
        return self._to_record(row) if row else None

    def add(self, record: InvitationRecord) -> None:
        self._session.add(self._to_model(record))
        self._session.flush()

    def save(self, record: InvitationRecord) -> None:
        row = self._session.get(InvitationModel, record.id)
        if row is None:
            self.add(record)
            return
        row.kind = record.kind
        row.name = record.name
        row.email = record.email
        row.building_name = record.building_name
        row.role_key = record.role_key
        row.client_id = record.client_id
        row.invited_by_user_id = record.invited_by_user_id
        row.token = record.token
        row.sent_at = _parse(record.sent_at)
        row.opened_at = _parse(record.opened_at)
        row.registered_at = _parse(record.registered_at)
        row.created_at = _parse(record.created_at) or datetime.now(timezone.utc).replace(tzinfo=None)
        self._session.flush()

    def delete(self, invitation_id: str) -> None:
        row = self._session.get(InvitationModel, invitation_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    def _to_record(self, row: InvitationModel) -> InvitationRecord:
        return InvitationRecord(
            id=row.id,
            kind=row.kind,
            name=row.name,
            email=row.email,
            building_name=row.building_name or "",
            role_key=row.role_key or "",
            client_id=row.client_id,
            invited_by_user_id=row.invited_by_user_id,
            token=row.token,
            sent_at=_iso(row.sent_at),
            opened_at=_iso(row.opened_at),
            registered_at=_iso(row.registered_at),
            created_at=_iso(row.created_at) or "",
        )

    def _to_model(self, record: InvitationRecord) -> InvitationModel:
        return InvitationModel(
            id=record.id,
            kind=record.kind,
            name=record.name,
            email=record.email,
            building_name=record.building_name,
            role_key=record.role_key,
            client_id=record.client_id,
            invited_by_user_id=record.invited_by_user_id,
            token=record.token,
            sent_at=_parse(record.sent_at),
            opened_at=_parse(record.opened_at),
            registered_at=_parse(record.registered_at),
            created_at=_parse(record.created_at) or datetime.now(timezone.utc).replace(tzinfo=None),
        )


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed
