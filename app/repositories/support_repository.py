"""Persistence for support tickets and messages."""

from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.support import SupportMessageRecord, SupportTicketRecord
from app.models.access import ClientModel, UserModel
from app.models.support import SupportMessageModel, SupportTicketModel


class SupportRepository(Protocol):
    """Persistence port used by the support service."""

    def list_tickets(self, *, client_id: str | None = None) -> list[SupportTicketRecord]:
        """Return tickets, optionally limited to one building."""

    def get_ticket(self, ticket_id: str) -> SupportTicketRecord | None:
        """Return one ticket with messages."""

    def add_ticket(self, ticket: SupportTicketRecord) -> None:
        """Insert a ticket and its first message when provided."""

    def add_message(self, message: SupportMessageRecord) -> None:
        """Append one message and bump the ticket updated_at."""

    def save_ticket_status(self, ticket_id: str, status: str) -> None:
        """Update ticket status."""


class SqlSupportRepository:
    """SQLAlchemy adapter for support tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_tickets(self, *, client_id: str | None = None) -> list[SupportTicketRecord]:
        query = select(SupportTicketModel).order_by(SupportTicketModel.updated_at.desc())
        if client_id is not None:
            query = query.where(SupportTicketModel.client_id == client_id)
        rows = self._session.execute(query).scalars().all()
        return [self._ticket(row, include_messages=False) for row in rows]

    def get_ticket(self, ticket_id: str) -> SupportTicketRecord | None:
        row = self._session.get(SupportTicketModel, ticket_id)
        if row is None:
            return None
        return self._ticket(row, include_messages=True)

    def add_ticket(self, ticket: SupportTicketRecord) -> None:
        self._session.add(
            SupportTicketModel(
                id=ticket.id,
                client_id=ticket.client_id,
                created_by_user_id=ticket.created_by_user_id,
                subject=ticket.subject,
                status=ticket.status,
            ),
        )
        self._session.flush()
        for message in ticket.messages:
            self.add_message(message)
        self._session.flush()

    def add_message(self, message: SupportMessageRecord) -> None:
        self._session.add(
            SupportMessageModel(
                id=message.id,
                ticket_id=message.ticket_id,
                author_user_id=message.author_user_id,
                body=message.body,
                from_staff=message.from_staff,
            ),
        )
        ticket = self._session.get(SupportTicketModel, message.ticket_id)
        if ticket is not None:
            ticket.updated_at = datetime.now(timezone.utc)
        self._session.flush()

    def save_ticket_status(self, ticket_id: str, status: str) -> None:
        row = self._session.get(SupportTicketModel, ticket_id)
        if row is None:
            raise KeyError(ticket_id)
        row.status = status
        row.updated_at = datetime.now(timezone.utc)

    def _ticket(self, row: SupportTicketModel, *, include_messages: bool) -> SupportTicketRecord:
        client_name = ""
        if row.client_id:
            client = self._session.get(ClientModel, row.client_id)
            client_name = client.name if client is not None else ""
        author = self._session.get(UserModel, row.created_by_user_id)
        messages: tuple[SupportMessageRecord, ...] = ()
        if include_messages:
            message_rows = self._session.execute(
                select(SupportMessageModel)
                .where(SupportMessageModel.ticket_id == row.id)
                .order_by(SupportMessageModel.created_at.asc(), SupportMessageModel.id.asc()),
            ).scalars().all()
            messages = tuple(self._message(item) for item in message_rows)
        return SupportTicketRecord(
            id=row.id,
            client_id=row.client_id,
            client_name=client_name,
            created_by_user_id=row.created_by_user_id,
            created_by_name=author.full_name if author is not None else "",
            subject=row.subject,
            status=row.status,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
            messages=messages,
        )

    def _message(self, row: SupportMessageModel) -> SupportMessageRecord:
        author = self._session.get(UserModel, row.author_user_id)
        return SupportMessageRecord(
            id=row.id,
            ticket_id=row.ticket_id,
            author_user_id=row.author_user_id,
            author_name=author.full_name if author is not None else "",
            body=row.body,
            created_at=row.created_at.isoformat() if row.created_at else "",
            from_staff=row.from_staff,
        )
