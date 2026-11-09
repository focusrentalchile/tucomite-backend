"""Use cases for platform support tickets."""

from datetime import datetime, timezone
from uuid import uuid4

from app.domain.support import (
    CREATABLE_SUPPORT_TYPE_NAMES,
    SUPPORT_STATUS_ANSWERED,
    SUPPORT_STATUS_OPEN,
    SUPPORT_TYPE_MESSAGE,
    SUPPORT_TYPE_SUPPORT,
    InvalidSupportType,
    SupportEmailError,
    SupportReplyRecord,
    SupportTicketNotFound,
    SupportTicketRecord,
    SupportTypeNotFound,
    SupportTypeRecord,
)
from app.repositories.support_repository import SupportRepository
from app.services.email_service import (
    EmailNotConfigured,
    EmailSendError,
    build_support_reply_html,
    send_html_email,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupportService:
    """Building and public-web support tickets for the platform inbox."""

    def __init__(self, repository: SupportRepository) -> None:
        self._repository = repository

    def list_types(self, *, creatable_only: bool = False) -> list[SupportTypeRecord]:
        """Support types; optionally only those buildings may open."""
        types = self._repository.list_types()
        if not creatable_only:
            return types
        return [item for item in types if item.name in CREATABLE_SUPPORT_TYPE_NAMES]

    def list_for_super_admin(self) -> list[SupportTicketRecord]:
        """Every ticket for the platform inbox."""
        return self._repository.list_all_tickets()

    def list_for_client(self, client_id: str) -> list[SupportTicketRecord]:
        """Tickets belonging to one building."""
        return self._repository.list_tickets_for_client(client_id)

    def get(self, ticket_id: str) -> SupportTicketRecord:
        """Load one ticket or raise."""
        record = self._repository.get_ticket(ticket_id)
        if record is None:
            raise SupportTicketNotFound()
        return record

    def create_building_ticket(
        self,
        *,
        client_id: str,
        author_user_id: str,
        author_name: str,
        subject: str,
        body: str,
        support_type_id: str | None = None,
    ) -> SupportTicketRecord:
        """Open a Soporte ticket from committee or client (type is assigned server-side)."""
        if support_type_id:
            support_type = self._repository.get_type(support_type_id)
        else:
            support_type = self._repository.get_type_by_name(SUPPORT_TYPE_SUPPORT)
        if support_type is None:
            raise SupportTypeNotFound()
        if support_type.name not in CREATABLE_SUPPORT_TYPE_NAMES:
            raise InvalidSupportType()
        cleaned_subject = subject.strip()
        cleaned_body = body.strip()
        if not cleaned_subject or not cleaned_body:
            raise ValueError("Subject and body are required.")
        now = _now()
        ticket_id = str(uuid4())
        record = SupportTicketRecord(
            id=ticket_id,
            client_id=client_id,
            author_user_id=author_user_id,
            author_name=author_name,
            support_type_id=support_type.id,
            support_type_name=support_type.name,
            subject=cleaned_subject,
            body=cleaned_body,
            status=SUPPORT_STATUS_OPEN,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_ticket(record)
        return self.get(ticket_id)

    def create_web_message_ticket(
        self,
        *,
        contact_name: str,
        contact_email: str,
        message: str,
    ) -> SupportTicketRecord:
        """Open a Mensaje ticket from the public contact form."""
        support_type = self._repository.get_type_by_name(SUPPORT_TYPE_MESSAGE)
        if support_type is None:
            raise SupportTypeNotFound()
        cleaned_name = contact_name.strip()
        cleaned_email = contact_email.strip().lower()
        cleaned_message = message.strip()
        subject = f"Mensaje web de {cleaned_name}"[:160]
        now = _now()
        ticket_id = str(uuid4())
        record = SupportTicketRecord(
            id=ticket_id,
            support_type_id=support_type.id,
            support_type_name=support_type.name,
            subject=subject,
            body=cleaned_message,
            status=SUPPORT_STATUS_OPEN,
            contact_name=cleaned_name,
            contact_email=cleaned_email,
            author_name=cleaned_name,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_ticket(record)
        return self.get(ticket_id)

    def add_reply(
        self,
        ticket_id: str,
        *,
        author_user_id: str,
        author_name: str,
        body: str,
        from_staff: bool,
        site_url: str = "https://tucomite.cl",
    ) -> SupportTicketRecord:
        """Append a chat reply; staff replies to Mensaje also email the visitor."""
        ticket = self.get(ticket_id)
        cleaned = body.strip()
        if not cleaned:
            raise ValueError("Reply body is required.")
        now = _now()
        reply = SupportReplyRecord(
            id=str(uuid4()),
            ticket_id=ticket_id,
            author_user_id=author_user_id,
            author_name=author_name,
            body=cleaned,
            from_staff=from_staff,
            created_at=now,
        )
        self._repository.add_reply(reply)
        status = ticket.status
        if from_staff and ticket.status == SUPPORT_STATUS_OPEN:
            status = SUPPORT_STATUS_ANSWERED
        elif not from_staff and ticket.status == SUPPORT_STATUS_ANSWERED:
            status = SUPPORT_STATUS_OPEN
        updated = SupportTicketRecord(
            id=ticket.id,
            client_id=ticket.client_id,
            author_user_id=ticket.author_user_id,
            author_name=ticket.author_name,
            support_type_id=ticket.support_type_id,
            support_type_name=ticket.support_type_name,
            subject=ticket.subject,
            body=ticket.body,
            status=status,
            contact_name=ticket.contact_name,
            contact_email=ticket.contact_email,
            created_at=ticket.created_at,
            updated_at=now,
            replies=ticket.replies + (reply,),
        )
        self._repository.save_ticket(updated)
        if from_staff and ticket.support_type_name == SUPPORT_TYPE_MESSAGE:
            email = (ticket.contact_email or "").strip()
            if not email:
                raise SupportEmailError("Contact email is missing for this web message.")
            html_body = build_support_reply_html(
                visitor_name=ticket.contact_name or "",
                reply_body=cleaned,
                site_url=site_url,
            )
            try:
                send_html_email(
                    to_email=email,
                    subject=f"Respuesta de Tu Comité: {ticket.subject}",
                    html_body=html_body,
                )
            except EmailNotConfigured as error:
                raise SupportEmailError(str(error)) from error
            except EmailSendError as error:
                raise SupportEmailError(str(error)) from error
        return self.get(ticket_id)
