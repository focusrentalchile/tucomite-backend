"""Unit tests for platform support tickets and web Mensaje replies."""

from unittest.mock import patch

import pytest

from app.domain.support import (
    SUPPORT_STATUS_ANSWERED,
    SUPPORT_STATUS_RESOLVED,
    SUPPORT_STATUS_SENT,
    SUPPORT_TYPE_MESSAGE,
    SUPPORT_TYPE_SUPPORT,
    InvalidSupportType,
    SupportAttachmentRecord,
    SupportEmailError,
    SupportReplyRecord,
    SupportStatusRecord,
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
        self.attachments: dict[str, list[SupportAttachmentRecord]] = {}

    def ensure_default_types(self) -> None:
        return None

    def ensure_default_statuses(self) -> None:
        return None

    def list_statuses(self) -> list[SupportStatusRecord]:
        return [
            SupportStatusRecord(key=SUPPORT_STATUS_SENT, label="Enviado"),
            SupportStatusRecord(key=SUPPORT_STATUS_ANSWERED, label="Respondido"),
            SupportStatusRecord(key=SUPPORT_STATUS_RESOLVED, label="Resuelto"),
        ]

    def list_types(self) -> list[SupportTypeRecord]:
        return list(self.types)

    def get_type(self, type_id: str) -> SupportTypeRecord | None:
        return next((item for item in self.types if item.id == type_id), None)

    def get_type_by_name(self, name: str) -> SupportTypeRecord | None:
        return next((item for item in self.types if item.name == name), None)

    def list_all_tickets(self) -> list[SupportTicketRecord]:
        return [self._with_attachments(item) for item in self.tickets.values()]

    def list_tickets_for_client(self, client_id: str) -> list[SupportTicketRecord]:
        return [
            self._with_attachments(item)
            for item in self.tickets.values()
            if item.client_id == client_id
        ]

    def list_tickets_for_author(self, author_user_id: str) -> list[SupportTicketRecord]:
        return [
            self._with_attachments(item)
            for item in self.tickets.values()
            if item.author_user_id == author_user_id
        ]

    def get_ticket(self, ticket_id: str) -> SupportTicketRecord | None:
        record = self.tickets.get(ticket_id)
        if record is None:
            return None
        return self._with_attachments(record)

    def add_ticket(self, record: SupportTicketRecord) -> None:
        self.tickets[record.id] = record

    def save_ticket(self, record: SupportTicketRecord) -> None:
        self.tickets[record.id] = record

    def delete_ticket(self, ticket_id: str) -> bool:
        return self.tickets.pop(ticket_id, None) is not None

    def add_reply(self, record: SupportReplyRecord) -> None:
        current = self.tickets[record.ticket_id]
        self.tickets[record.ticket_id] = SupportTicketRecord(
            **{**current.__dict__, "replies": (*current.replies, record)},
        )

    def get_reply(self, reply_id: str) -> SupportReplyRecord | None:
        for ticket in self.tickets.values():
            for reply in ticket.replies:
                if reply.id == reply_id:
                    return reply
        return None

    def update_reply(self, reply_id: str, body: str) -> SupportReplyRecord | None:
        for ticket_id, ticket in self.tickets.items():
            updated: list[SupportReplyRecord] = []
            found = None
            for reply in ticket.replies:
                if reply.id == reply_id:
                    found = SupportReplyRecord(**{**reply.__dict__, "body": body})
                    updated.append(found)
                else:
                    updated.append(reply)
            if found is not None:
                self.tickets[ticket_id] = SupportTicketRecord(
                    **{**ticket.__dict__, "replies": tuple(updated)},
                )
                return found
        return None

    def delete_reply(self, reply_id: str) -> bool:
        for ticket_id, ticket in self.tickets.items():
            kept = tuple(reply for reply in ticket.replies if reply.id != reply_id)
            if len(kept) != len(ticket.replies):
                self.tickets[ticket_id] = SupportTicketRecord(
                    **{**ticket.__dict__, "replies": kept},
                )
                return True
        return False

    def replace_attachments(
        self,
        ticket_id: str,
        attachments: list[SupportAttachmentRecord],
    ) -> None:
        self.attachments[ticket_id] = list(attachments)

    def _with_attachments(self, record: SupportTicketRecord) -> SupportTicketRecord:
        return SupportTicketRecord(
            **{
                **record.__dict__,
                "attachments": tuple(self.attachments.get(record.id, [])),
            },
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
        attachments=[
            {"kind": "image", "name": "foto.png", "url": "data:image/png;base64,abc"},
            {"kind": "file", "name": "nota.pdf", "url": "data:application/pdf;base64,xyz"},
        ],
    )
    assert created.status == SUPPORT_STATUS_SENT
    assert created.support_type_name == SUPPORT_TYPE_SUPPORT
    assert len(created.attachments) == 2
    assert created.attachments[0].name == "foto.png"

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
    assert len(replied.attachments) == 2

    reply_id = replied.replies[0].id
    edited = service.update_reply(
        created.id,
        reply_id,
        body="Actualizado",
        actor_user_id="staff",
        is_super_admin=True,
    )
    assert edited.replies[0].body == "Actualizado"
    cleared = service.delete_reply(
        created.id,
        reply_id,
        actor_user_id="staff",
        is_super_admin=True,
    )
    assert cleared.replies == ()
    resolved = service.update_status(
        created.id,
        status=SUPPORT_STATUS_RESOLVED,
        is_super_admin=True,
    )
    assert resolved.status == SUPPORT_STATUS_RESOLVED
    with pytest.raises(ValueError, match="Resolved"):
        service.add_reply(
            created.id,
            author_user_id="staff",
            author_name="Tu Comité",
            body="No debería",
            from_staff=True,
        )


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
