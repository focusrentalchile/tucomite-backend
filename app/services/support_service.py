"""Use cases for platform support tickets."""

import uuid
from datetime import datetime, timezone

from app.domain.support import SupportMessageRecord, SupportTicketRecord, TicketNotFound
from app.repositories.support_repository import SupportRepository

ALLOWED_STATUSES = frozenset({"open", "pending", "resolved", "closed"})


class SupportService:
    """Creates tickets and keeps the conversation thread."""

    def __init__(self, repository: SupportRepository) -> None:
        self._repository = repository

    def list_tickets(self, *, client_id: str | None = None) -> list[SupportTicketRecord]:
        """Return tickets for one building, or every ticket when client_id is None."""
        return self._repository.list_tickets(client_id=client_id)

    def get_ticket(self, ticket_id: str) -> SupportTicketRecord:
        """Return one ticket with messages."""
        ticket = self._repository.get_ticket(ticket_id)
        if ticket is None:
            raise TicketNotFound()
        return ticket

    def create_ticket(
        self,
        *,
        subject: str,
        body: str,
        created_by_user_id: str,
        created_by_name: str,
        client_id: str | None,
        client_name: str,
        from_staff: bool,
    ) -> SupportTicketRecord:
        """Open a ticket with the first message."""
        cleaned_subject = subject.strip()
        cleaned_body = body.strip()
        if not cleaned_subject or not cleaned_body:
            raise ValueError("Subject and body are required.")
        now = datetime.now(timezone.utc).isoformat()
        ticket_id = str(uuid.uuid4())
        message = SupportMessageRecord(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            author_user_id=created_by_user_id,
            author_name=created_by_name,
            body=cleaned_body,
            created_at=now,
            from_staff=from_staff,
        )
        ticket = SupportTicketRecord(
            id=ticket_id,
            client_id=client_id,
            client_name=client_name,
            created_by_user_id=created_by_user_id,
            created_by_name=created_by_name,
            subject=cleaned_subject,
            status="open",
            created_at=now,
            updated_at=now,
            messages=(message,),
        )
        self._repository.add_ticket(ticket)
        return self.get_ticket(ticket_id)

    def add_message(
        self,
        ticket_id: str,
        *,
        body: str,
        author_user_id: str,
        author_name: str,
        from_staff: bool,
    ) -> SupportTicketRecord:
        """Append a reply to an existing ticket."""
        ticket = self.get_ticket(ticket_id)
        cleaned_body = body.strip()
        if not cleaned_body:
            raise ValueError("Message body is required.")
        message = SupportMessageRecord(
            id=str(uuid.uuid4()),
            ticket_id=ticket.id,
            author_user_id=author_user_id,
            author_name=author_name,
            body=cleaned_body,
            created_at=datetime.now(timezone.utc).isoformat(),
            from_staff=from_staff,
        )
        self._repository.add_message(message)
        if ticket.status == "resolved" or ticket.status == "closed":
            self._repository.save_ticket_status(ticket.id, "open")
        elif from_staff and ticket.status == "open":
            self._repository.save_ticket_status(ticket.id, "pending")
        return self.get_ticket(ticket_id)

    def set_status(self, ticket_id: str, status: str) -> SupportTicketRecord:
        """Change ticket status when the value is allowed."""
        cleaned = status.strip().lower()
        if cleaned not in ALLOWED_STATUSES:
            raise ValueError("Unknown ticket status.")
        self.get_ticket(ticket_id)
        self._repository.save_ticket_status(ticket_id, cleaned)
        return self.get_ticket(ticket_id)
