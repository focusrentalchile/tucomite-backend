"""Unit tests for platform support tickets and web Mensaje replies."""

from unittest.mock import patch

import pytest

from app.domain.support import (
    SUPPORT_STATUS_ANSWERED,
    SUPPORT_STATUS_OPEN,
    SUPPORT_TYPE_MESSAGE,
    SUPPORT_TYPE_SUPPORT,
    InvalidSupportType,
    SupportEmailError,
    SupportReplyRecord,
    SupportTicketRecord,
    SupportTypeRecord,
)
from app.services.support_service import SupportService


class MemorySupportRepository:
    def __init__(self) -> None:
        self.types = [
            SupportTypeRecord(id="t1", name=SUPPORT_TYPE_SUPPORT),
            SupportTypeRecord(id="tm", name=SUPPORT_TYPE_MESSAGE),
        ]
        self.tickets: dict[str, SupportTicketRecord] = {}

    def ensure_default_types(self) -> None:
        return None

    def list_types(self) -> list[SupportTypeRecord]:
        return list(self.types)

    def get_type(self, type_id: str) -> SupportTypeRecord | None:
        return next((item for item in self.types if item.id == type_id), None)

    def get_type_by_name(self, name: str) -> SupportTypeRecord | None:
        return next((item for item in self.types if item.name == name), None)

    def list_all_tickets(self) -> list[SupportTicketRecord]:
        return list(self.tickets.values())

    def list_tickets_for_client(self, client_id: str) -> list[SupportTicketRecord]:
        return [item for item in self.tickets.values() if item.client_id == client_id]

    def list_tickets_for_author(self, author_user_id: str) -> list[SupportTicketRecord]:
        return [item for item in self.tickets.values() if item.author_user_id == author_user_id]

    def get_ticket(self, ticket_id: str) -> SupportTicketRecord | None:
        return self.tickets.get(ticket_id)

    def add_ticket(self, record: SupportTicketRecord) -> None:
        self.tickets[record.id] = record

    def save_ticket(self, record: SupportTicketRecord) -> None:
        self.tickets[record.id] = record

    def add_reply(self, record: SupportReplyRecord) -> None:
        current = self.tickets[record.ticket_id]
        self.tickets[record.ticket_id] = SupportTicketRecord(
            **{**current.__dict__, "replies": (*current.replies, record)},
        )


def test_building_ticket_rejects_mensaje_type() -> None:
    service = SupportService(MemorySupportRepository())
    with pytest.raises(InvalidSupportType):
        service.create_building_ticket(
            client_id="c1",
            author_user_id="u1",
            author_name="Comité",
            support_type_id="tm",
            subject="Hola",
            body="No debería",
        )


def test_create_and_reply_chat() -> None:
    repo = MemorySupportRepository()
    service = SupportService(repo)
    created = service.create_building_ticket(
        client_id="c1",
        author_user_id="u1",
        author_name="Comité",
        subject="Ayuda",
        body="Necesito asistencia",
    )
    assert created.status == SUPPORT_STATUS_OPEN
    assert created.support_type_name == SUPPORT_TYPE_SUPPORT

    replied = service.add_reply(
        created.id,
        author_user_id="staff",
        author_name="Tu Comité",
        body="Estamos en eso",
        from_staff=True,
    )
    assert replied.status == SUPPORT_STATUS_ANSWERED
    assert len(replied.replies) == 1
    assert replied.replies[0].from_staff is True


def test_web_message_staff_reply_sends_email() -> None:
    repo = MemorySupportRepository()
    service = SupportService(repo)
    ticket = service.create_web_message_ticket(
        contact_name="Ana",
        contact_email="ana@edificio.cl",
        message="Quiero una demo",
    )
    assert ticket.support_type_name == SUPPORT_TYPE_MESSAGE

    with patch("app.services.support_service.send_html_email") as send_mail:
        updated = service.add_reply(
            ticket.id,
            author_user_id="staff",
            author_name="Tu Comité",
            body="Gracias por escribirnos",
            from_staff=True,
        )
        send_mail.assert_called_once()
        assert send_mail.call_args.kwargs["to_email"] == "ana@edificio.cl"
    assert updated.status == SUPPORT_STATUS_ANSWERED


def test_web_message_reply_without_smtp_raises() -> None:
    repo = MemorySupportRepository()
    service = SupportService(repo)
    ticket = service.create_web_message_ticket(
        contact_name="Ana",
        contact_email="ana@edificio.cl",
        message="Hola",
    )
    with patch(
        "app.services.support_service.send_html_email",
        side_effect=__import__("app.services.email_service", fromlist=["EmailNotConfigured"]).EmailNotConfigured(
            "SMTP is not configured.",
        ),
    ):
        with pytest.raises(SupportEmailError):
            service.add_reply(
                ticket.id,
                author_user_id="staff",
                author_name="Tu Comité",
                body="Respuesta",
                from_staff=True,
            )
