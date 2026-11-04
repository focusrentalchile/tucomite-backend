"""Unit tests for resident message status flow."""

from app.domain.messages import (
    MESSAGE_STATUS_FINISHED,
    MESSAGE_STATUS_IN_RESOLUTION,
    MESSAGE_STATUS_SEEN,
    MESSAGE_STATUS_SENT,
    MessageAttachmentRecord,
    MessageRecord,
    MessageStatusEventRecord,
    MessageTypeRecord,
)
from app.services.message_service import MessageService


class MemoryMessageRepository:
    def __init__(self) -> None:
        self.types = [MessageTypeRecord(id="t1", name="Consulta"), MessageTypeRecord(id="t2", name="Incidencia")]
        self.messages: dict[str, MessageRecord] = {}
        self.events: list[MessageStatusEventRecord] = []

    def ensure_default_types(self) -> None:
        return None

    def list_types(self) -> list[MessageTypeRecord]:
        return sorted(self.types, key=lambda item: item.name)

    def get_type(self, type_id: str) -> MessageTypeRecord | None:
        return next((item for item in self.types if item.id == type_id), None)

    def list_messages_for_author(self, author_user_id: str) -> list[MessageRecord]:
        return [item for item in self.messages.values() if item.author_user_id == author_user_id]

    def list_messages_for_viewer(self, user_id: str) -> list[MessageRecord]:
        return [
            item
            for item in self.messages.values()
            if item.author_user_id == user_id
            or any(person.user_id == user_id for person in item.participants)
        ]

    def list_messages_for_client(self, client_id: str) -> list[MessageRecord]:
        return [item for item in self.messages.values() if item.client_id == client_id]

    def get_message(self, message_id: str) -> MessageRecord | None:
        return self.messages.get(message_id)

    def add_message(self, record: MessageRecord) -> None:
        self.messages[record.id] = record

    def save_message(self, record: MessageRecord) -> None:
        self.messages[record.id] = record

    def delete_message(self, message_id: str) -> None:
        self.messages.pop(message_id, None)

    def replace_message_attachments(
        self,
        message_id: str,
        attachments: list[MessageAttachmentRecord],
    ) -> None:
        current = self.messages[message_id]
        self.messages[message_id] = MessageRecord(
            **{**current.__dict__, "attachments": tuple(attachments)},
        )

    def replace_participants(self, message_id: str, user_ids: list[str]) -> None:
        from app.domain.messages import MessageParticipantRecord

        current = self.messages[message_id]
        self.messages[message_id] = MessageRecord(
            **{
                **current.__dict__,
                "participants": tuple(
                    MessageParticipantRecord(user_id=user_id, full_name="") for user_id in user_ids
                ),
            },
        )

    def add_reply(self, reply) -> None:
        current = self.messages[reply.message_id]
        self.messages[reply.message_id] = MessageRecord(
            **{**current.__dict__, "replies": (*current.replies, reply)},
        )

    def add_status_event(self, event: MessageStatusEventRecord) -> None:
        self.events.append(event)


def test_open_and_reply_move_status() -> None:
    repo = MemoryMessageRepository()
    service = MessageService(repo)
    created = service.create(
        client_id="c1",
        author_user_id="u1",
        author_name="Residente",
        message_type_id="t1",
        subject="Ascensor",
        body="No funciona",
    )
    assert created.status == MESSAGE_STATUS_SENT
    seen = service.open_by_admin(created.id)
    assert seen.status == MESSAGE_STATUS_SEEN
    replied = service.add_reply(
        created.id,
        author_user_id="admin",
        author_name="Admin",
        body="Vamos a revisar",
        from_admin=True,
    )
    assert replied.status == MESSAGE_STATUS_IN_RESOLUTION
    finished = service.set_status(created.id, MESSAGE_STATUS_FINISHED)
    assert finished.status == MESSAGE_STATUS_FINISHED
    assert len(repo.events) >= 3


def test_create_with_participants_is_visible_read_only_to_invitee() -> None:
    repo = MemoryMessageRepository()
    service = MessageService(repo)
    created = service.create(
        client_id="c1",
        author_user_id="u1",
        author_name="Residente 1",
        message_type_id="t1",
        subject="Ruido",
        body="En el piso 3",
        participant_user_ids=["u2", "u1", "u2"],
    )
    assert [person.user_id for person in created.participants] == ["u2"]
    assert service.can_view(created, "u1") is True
    assert service.can_view(created, "u2") is True
    assert service.can_view(created, "u3") is False
    listed = service.list_for_viewer("u2")
    assert [item.id for item in listed] == [created.id]
