"""Persistence for platform support tickets."""

from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.support import (
    DEFAULT_SUPPORT_STATUSES,
    DEFAULT_SUPPORT_TYPE_NAMES,
    LEGACY_SUPPORT_STATUS_RENAMES,
    SupportAttachmentRecord,
    SupportReplyRecord,
    SupportStatusRecord,
    SupportTicketRecord,
    SupportTypeRecord,
)
from app.models.access import UserModel
from app.models.support import (
    SupportAttachmentModel,
    SupportReplyModel,
    SupportStatusModel,
    SupportTicketModel,
    SupportTypeModel,
)


def _iso(value: datetime | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.isoformat()


class SupportRepository(Protocol):
    """Port used by SupportService."""

    def ensure_default_types(self) -> None: ...

    def ensure_default_statuses(self) -> None: ...

    def list_statuses(self) -> list[SupportStatusRecord]: ...

    def list_types(self) -> list[SupportTypeRecord]: ...

    def get_type(self, type_id: str) -> SupportTypeRecord | None: ...

    def get_type_by_name(self, name: str) -> SupportTypeRecord | None: ...

    def list_all_tickets(self) -> list[SupportTicketRecord]: ...

    def list_tickets_for_client(self, client_id: str) -> list[SupportTicketRecord]: ...

    def list_tickets_for_author(self, author_user_id: str) -> list[SupportTicketRecord]: ...

    def get_ticket(self, ticket_id: str) -> SupportTicketRecord | None: ...

    def add_ticket(self, record: SupportTicketRecord) -> None: ...

    def save_ticket(self, record: SupportTicketRecord) -> None: ...

    def delete_ticket(self, ticket_id: str) -> bool: ...

    def add_reply(self, record: SupportReplyRecord) -> None: ...

    def update_reply(self, reply_id: str, body: str) -> SupportReplyRecord | None: ...

    def delete_reply(self, reply_id: str) -> bool: ...

    def get_reply(self, reply_id: str) -> SupportReplyRecord | None: ...

    def replace_attachments(
        self,
        ticket_id: str,
        attachments: list[SupportAttachmentRecord],
    ) -> None: ...


class SqlSupportRepository:
    """SQLAlchemy adapter for support tickets."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_default_types(self) -> None:
        from app.domain.support import LEGACY_SUPPORT_TYPE_RENAMES

        rows = list(self._session.scalars(select(SupportTypeModel)).all())
        for row in rows:
            renamed = LEGACY_SUPPORT_TYPE_RENAMES.get(row.name)
            if renamed is not None and renamed != row.name:
                # Prefer a single canonical "Soporte" row when renaming duplicates.
                already = next((item for item in rows if item.name == renamed), None)
                if already is None:
                    row.name = renamed
                # Leave the duplicate legacy row; tickets still resolve by id.
        existing = {row.name for row in self._session.scalars(select(SupportTypeModel)).all()}
        for name in DEFAULT_SUPPORT_TYPE_NAMES:
            if name in existing:
                continue
            self._session.add(SupportTypeModel(id=str(uuid4()), name=name))
        self._session.flush()

    def ensure_default_statuses(self) -> None:
        existing = {
            row.key: row for row in self._session.scalars(select(SupportStatusModel)).all()
        }
        for key, label in DEFAULT_SUPPORT_STATUSES:
            row = existing.get(key)
            if row is None:
                self._session.add(SupportStatusModel(key=key, label=label))
            elif row.label != label:
                row.label = label
        for ticket in self._session.scalars(select(SupportTicketModel)).all():
            renamed = LEGACY_SUPPORT_STATUS_RENAMES.get(ticket.status)
            if renamed is not None and renamed != ticket.status:
                ticket.status = renamed
        self._session.flush()

    def list_statuses(self) -> list[SupportStatusRecord]:
        self.ensure_default_statuses()
        order = {key: index for index, (key, _) in enumerate(DEFAULT_SUPPORT_STATUSES)}
        rows = list(self._session.scalars(select(SupportStatusModel)).all())
        rows.sort(key=lambda row: order.get(row.key, 99))
        return [SupportStatusRecord(key=row.key, label=row.label) for row in rows]

    def list_types(self) -> list[SupportTypeRecord]:
        self.ensure_default_types()
        rows = self._session.scalars(select(SupportTypeModel).order_by(SupportTypeModel.name)).all()
        return [SupportTypeRecord(id=row.id, name=row.name) for row in rows]

    def get_type(self, type_id: str) -> SupportTypeRecord | None:
        row = self._session.get(SupportTypeModel, type_id)
        if row is None:
            return None
        return SupportTypeRecord(id=row.id, name=row.name)

    def get_type_by_name(self, name: str) -> SupportTypeRecord | None:
        self.ensure_default_types()
        row = self._session.scalars(
            select(SupportTypeModel).where(SupportTypeModel.name == name),
        ).first()
        if row is None:
            return None
        return SupportTypeRecord(id=row.id, name=row.name)

    def list_all_tickets(self) -> list[SupportTicketRecord]:
        rows = self._session.scalars(
            select(SupportTicketModel).order_by(SupportTicketModel.created_at.desc()),
        ).all()
        return [self._ticket(row) for row in rows]

    def list_tickets_for_client(self, client_id: str) -> list[SupportTicketRecord]:
        rows = self._session.scalars(
            select(SupportTicketModel)
            .where(SupportTicketModel.client_id == client_id)
            .order_by(SupportTicketModel.created_at.desc()),
        ).all()
        return [self._ticket(row) for row in rows]

    def list_tickets_for_author(self, author_user_id: str) -> list[SupportTicketRecord]:
        rows = self._session.scalars(
            select(SupportTicketModel)
            .where(SupportTicketModel.author_user_id == author_user_id)
            .order_by(SupportTicketModel.created_at.desc()),
        ).all()
        return [self._ticket(row) for row in rows]

    def get_ticket(self, ticket_id: str) -> SupportTicketRecord | None:
        row = self._session.get(SupportTicketModel, ticket_id)
        if row is None:
            return None
        return self._ticket(row)

    def add_ticket(self, record: SupportTicketRecord) -> None:
        self._session.add(
            SupportTicketModel(
                id=record.id,
                client_id=record.client_id,
                author_user_id=record.author_user_id,
                support_type_id=record.support_type_id,
                subject=record.subject,
                body=record.body,
                status=record.status,
                contact_name=record.contact_name,
                contact_email=record.contact_email,
            ),
        )
        self._session.flush()

    def save_ticket(self, record: SupportTicketRecord) -> None:
        row = self._session.get(SupportTicketModel, record.id)
        if row is None:
            return
        row.status = record.status
        row.subject = record.subject
        row.body = record.body
        self._session.flush()

    def delete_ticket(self, ticket_id: str) -> bool:
        row = self._session.get(SupportTicketModel, ticket_id)
        if row is None:
            return False
        self._session.execute(
            delete(SupportAttachmentModel).where(SupportAttachmentModel.ticket_id == ticket_id),
        )
        self._session.execute(
            delete(SupportReplyModel).where(SupportReplyModel.ticket_id == ticket_id),
        )
        self._session.delete(row)
        self._session.flush()
        return True

    def add_reply(self, record: SupportReplyRecord) -> None:
        self._session.add(
            SupportReplyModel(
                id=record.id,
                ticket_id=record.ticket_id,
                author_user_id=record.author_user_id,
                body=record.body,
                from_staff=record.from_staff,
            ),
        )
        self._session.flush()

    def get_reply(self, reply_id: str) -> SupportReplyRecord | None:
        row = self._session.get(SupportReplyModel, reply_id)
        if row is None:
            return None
        author_name = "Tu Comité"
        if row.author_user_id:
            user = self._session.get(UserModel, row.author_user_id)
            if user is not None:
                author_name = user.full_name or user.email or author_name
        return SupportReplyRecord(
            id=row.id,
            ticket_id=row.ticket_id,
            author_user_id=row.author_user_id,
            author_name=author_name,
            body=row.body,
            from_staff=bool(row.from_staff),
            created_at=_iso(row.created_at),
        )

    def update_reply(self, reply_id: str, body: str) -> SupportReplyRecord | None:
        row = self._session.get(SupportReplyModel, reply_id)
        if row is None:
            return None
        row.body = body
        self._session.flush()
        return self.get_reply(reply_id)

    def delete_reply(self, reply_id: str) -> bool:
        row = self._session.get(SupportReplyModel, reply_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True

    def replace_attachments(
        self,
        ticket_id: str,
        attachments: list[SupportAttachmentRecord],
    ) -> None:
        self._session.execute(
            delete(SupportAttachmentModel).where(SupportAttachmentModel.ticket_id == ticket_id),
        )
        for item in attachments:
            self._session.add(
                SupportAttachmentModel(
                    id=item.id or str(uuid4()),
                    ticket_id=ticket_id,
                    kind=item.kind,
                    name=item.name,
                    url=item.url,
                ),
            )
        self._session.flush()

    def _ticket(self, row: SupportTicketModel) -> SupportTicketRecord:
        type_row = self._session.get(SupportTypeModel, row.support_type_id)
        author_name = ""
        if row.author_user_id:
            user = self._session.get(UserModel, row.author_user_id)
            if user is not None:
                author_name = user.full_name or user.email or ""
        elif row.contact_name:
            author_name = row.contact_name
        replies = self._replies(row.id)
        attachments = self._attachments(row.id)
        status_key = LEGACY_SUPPORT_STATUS_RENAMES.get(row.status, row.status)
        status_row = self._session.get(SupportStatusModel, status_key)
        status_label = status_row.label if status_row is not None else status_key
        return SupportTicketRecord(
            id=row.id,
            client_id=row.client_id,
            author_user_id=row.author_user_id,
            author_name=author_name,
            support_type_id=row.support_type_id,
            support_type_name=type_row.name if type_row is not None else "",
            subject=row.subject,
            body=row.body,
            status=status_key,
            status_label=status_label,
            contact_name=row.contact_name,
            contact_email=row.contact_email,
            created_at=_iso(row.created_at),
            updated_at=_iso(row.updated_at),
            attachments=tuple(attachments),
            replies=tuple(replies),
        )

    def _attachments(self, ticket_id: str) -> list[SupportAttachmentRecord]:
        rows = self._session.scalars(
            select(SupportAttachmentModel).where(SupportAttachmentModel.ticket_id == ticket_id),
        ).all()
        return [
            SupportAttachmentRecord(
                id=row.id,
                ticket_id=row.ticket_id,
                kind=row.kind,
                name=row.name,
                url=row.url,
            )
            for row in rows
        ]

    def _replies(self, ticket_id: str) -> list[SupportReplyRecord]:
        rows = self._session.scalars(
            select(SupportReplyModel)
            .where(SupportReplyModel.ticket_id == ticket_id)
            .order_by(SupportReplyModel.created_at.asc()),
        ).all()
        items: list[SupportReplyRecord] = []
        for row in rows:
            author_name = "Tu Comité"
            if row.author_user_id:
                user = self._session.get(UserModel, row.author_user_id)
                if user is not None:
                    author_name = user.full_name or user.email or author_name
            items.append(
                SupportReplyRecord(
                    id=row.id,
                    ticket_id=row.ticket_id,
                    author_user_id=row.author_user_id,
                    author_name=author_name,
                    body=row.body,
                    from_staff=bool(row.from_staff),
                    created_at=_iso(row.created_at),
                ),
            )
        return items
