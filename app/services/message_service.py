"""Use cases for resident building messages."""

from datetime import datetime, timezone
from uuid import uuid4

from app.domain.messages import (
    ATTACHMENT_KINDS,
    MESSAGE_STATUS_FINISHED,
    MESSAGE_STATUS_IN_RESOLUTION,
    MESSAGE_STATUS_SEEN,
    MESSAGE_STATUS_SENT,
    InvalidMessageStatus,
    MessageAttachmentRecord,
    MessageNotFound,
    MessageRecord,
    MessageReplyRecord,
    MessageStatusEventRecord,
    MessageTypeNotFound,
    MessageTypeRecord,
)
from app.domain.topics import MEDIUM_PRIORITY_ID
from app.repositories.message_repository import MessageRepository
from app.services.topic_service import TopicService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MessageService:
    """Resident messages for a building and administrator Gestión board."""

    def __init__(
        self,
        repository: MessageRepository,
        *,
        topic_service: TopicService | None = None,
    ) -> None:
        self._repository = repository
        self._topics = topic_service

    def list_types(self) -> list[MessageTypeRecord]:
        """Alphabetical message types for the create form."""
        return self._repository.list_types()

    def list_for_author(self, author_user_id: str) -> list[MessageRecord]:
        """Messages created by one resident."""
        return self._repository.list_messages_for_author(author_user_id)

    def list_for_client(self, client_id: str) -> list[MessageRecord]:
        """All messages for one building (administrator board)."""
        return self._repository.list_messages_for_client(client_id)

    def get(self, message_id: str) -> MessageRecord:
        """Load one message or raise."""
        record = self._repository.get_message(message_id)
        if record is None:
            raise MessageNotFound()
        return record

    def create(
        self,
        *,
        client_id: str,
        author_user_id: str,
        author_name: str,
        message_type_id: str,
        subject: str,
        body: str,
        attachments: list[dict[str, str]] | None = None,
        parent_message_id: str | None = None,
        topic_id: str | None = None,
    ) -> MessageRecord:
        """Open a new ticket in Enviado."""
        message_type = self._repository.get_type(message_type_id)
        if message_type is None:
            raise MessageTypeNotFound()
        now = _now()
        message_id = str(uuid4())
        record = MessageRecord(
            id=message_id,
            client_id=client_id,
            author_user_id=author_user_id,
            author_name=author_name,
            message_type_id=message_type.id,
            message_type_name=message_type.name,
            subject=subject.strip(),
            body=body.strip(),
            status=MESSAGE_STATUS_SENT,
            created_at=now,
            updated_at=now,
            sent_at=now,
            parent_message_id=parent_message_id,
            topic_id=topic_id,
            attachments=tuple(self._normalize_attachments(attachments)),
            status_events=(
                MessageStatusEventRecord(
                    id=str(uuid4()),
                    message_id=message_id,
                    status=MESSAGE_STATUS_SENT,
                    occurred_at=now,
                ),
            ),
        )
        self._repository.add_message(record)
        stored = self._repository.get_message(message_id)
        if stored is None:
            raise MessageNotFound()
        return stored

    def update(
        self,
        message_id: str,
        *,
        author_user_id: str,
        message_type_id: str,
        subject: str,
        body: str,
        attachments: list[dict[str, str]] | None = None,
    ) -> MessageRecord:
        """Edit a message while it is still Enviado."""
        current = self.get(message_id)
        if current.author_user_id != author_user_id:
            raise PermissionError("Only the author can edit this message.")
        if current.status != MESSAGE_STATUS_SENT:
            raise InvalidMessageStatus()
        message_type = self._repository.get_type(message_type_id)
        if message_type is None:
            raise MessageTypeNotFound()
        updated = MessageRecord(
            id=current.id,
            client_id=current.client_id,
            author_user_id=current.author_user_id,
            author_name=current.author_name,
            message_type_id=message_type.id,
            message_type_name=message_type.name,
            subject=subject.strip(),
            body=body.strip(),
            status=current.status,
            created_at=current.created_at,
            updated_at=_now(),
            sent_at=current.sent_at,
            seen_at=current.seen_at,
            in_resolution_at=current.in_resolution_at,
            finished_at=current.finished_at,
            parent_message_id=current.parent_message_id,
            topic_id=current.topic_id,
            attachments=tuple(self._normalize_attachments(attachments)),
            replies=current.replies,
            status_events=current.status_events,
        )
        self._repository.save_message(updated)
        self._repository.replace_message_attachments(message_id, list(updated.attachments))
        return self.get(message_id)

    def delete(self, message_id: str, *, author_user_id: str) -> None:
        """Remove a message while it is still Enviado."""
        current = self.get(message_id)
        if current.author_user_id != author_user_id:
            raise PermissionError("Only the author can delete this message.")
        if current.status != MESSAGE_STATUS_SENT:
            raise InvalidMessageStatus()
        self._repository.delete_message(message_id)

    def open_by_admin(self, message_id: str) -> MessageRecord:
        """Mark Enviado as Visto when the administrator opens the card."""
        current = self.get(message_id)
        if current.status != MESSAGE_STATUS_SENT:
            return current
        return self._move(current, MESSAGE_STATUS_SEEN)

    def set_status(self, message_id: str, status: str) -> MessageRecord:
        """Administrator moves the card to En resolución or Finalizada."""
        current = self.get(message_id)
        if status == MESSAGE_STATUS_IN_RESOLUTION:
            if current.status not in {MESSAGE_STATUS_SEEN, MESSAGE_STATUS_IN_RESOLUTION}:
                if current.status == MESSAGE_STATUS_SENT:
                    current = self._move(current, MESSAGE_STATUS_SEEN)
                else:
                    raise InvalidMessageStatus()
            if current.status == MESSAGE_STATUS_IN_RESOLUTION:
                return current
            return self._move(current, MESSAGE_STATUS_IN_RESOLUTION)
        if status == MESSAGE_STATUS_FINISHED:
            if current.status not in {
                MESSAGE_STATUS_IN_RESOLUTION,
                MESSAGE_STATUS_SEEN,
                MESSAGE_STATUS_FINISHED,
            }:
                raise InvalidMessageStatus()
            if current.status == MESSAGE_STATUS_FINISHED:
                return current
            if current.status == MESSAGE_STATUS_SEEN:
                current = self._move(current, MESSAGE_STATUS_IN_RESOLUTION)
            return self._move(current, MESSAGE_STATUS_FINISHED)
        raise InvalidMessageStatus()

    def add_reply(
        self,
        message_id: str,
        *,
        author_user_id: str,
        author_name: str,
        body: str,
        from_admin: bool,
        attachments: list[dict[str, str]] | None = None,
    ) -> MessageRecord:
        """Append a reply; admin replies advance Enviado/Visto to En resolución."""
        current = self.get(message_id)
        now = _now()
        reply = MessageReplyRecord(
            id=str(uuid4()),
            message_id=message_id,
            author_user_id=author_user_id,
            author_name=author_name,
            body=body.strip(),
            from_admin=from_admin,
            created_at=now,
            attachments=tuple(self._normalize_attachments(attachments)),
        )
        self._repository.add_reply(reply)
        if from_admin and current.status in {MESSAGE_STATUS_SENT, MESSAGE_STATUS_SEEN}:
            if current.status == MESSAGE_STATUS_SENT:
                current = self._move(current, MESSAGE_STATUS_SEEN)
            current = self._move(current, MESSAGE_STATUS_IN_RESOLUTION)
        return self.get(message_id)

    def appeal(
        self,
        message_id: str,
        *,
        author_user_id: str,
        author_name: str,
        body: str,
        attachments: list[dict[str, str]] | None = None,
        period_id: str | None = None,
    ) -> MessageRecord:
        """Resident appeals a finished ticket: create Tema + new Enviado message."""
        current = self.get(message_id)
        if current.author_user_id != author_user_id:
            raise PermissionError("Only the author can appeal this message.")
        if current.status != MESSAGE_STATUS_FINISHED:
            raise InvalidMessageStatus()
        if self._topics is None:
            raise ValueError("Topics are not available.")
        appeal_body = body.strip()
        decision = f"Apelación del mensaje: {current.subject}"
        topic = self._topics.create_topic(
            title=current.subject,
            description=appeal_body,
            category_key="other",
            attachment_name="",
            decision=decision,
            priority_id=MEDIUM_PRIORITY_ID,
            period_id=period_id,
            attachments=attachments,
        )
        return self.create(
            client_id=current.client_id,
            author_user_id=author_user_id,
            author_name=author_name,
            message_type_id=current.message_type_id,
            subject=f"Apelación: {current.subject}",
            body=appeal_body,
            attachments=attachments,
            parent_message_id=current.id,
            topic_id=topic.id,
        )

    def _move(self, current: MessageRecord, status: str) -> MessageRecord:
        now = _now()
        seen_at = current.seen_at
        in_resolution_at = current.in_resolution_at
        finished_at = current.finished_at
        if status == MESSAGE_STATUS_SEEN:
            seen_at = now
        elif status == MESSAGE_STATUS_IN_RESOLUTION:
            in_resolution_at = now
            if seen_at is None:
                seen_at = now
        elif status == MESSAGE_STATUS_FINISHED:
            finished_at = now
            if seen_at is None:
                seen_at = now
            if in_resolution_at is None:
                in_resolution_at = now
        updated = MessageRecord(
            id=current.id,
            client_id=current.client_id,
            author_user_id=current.author_user_id,
            author_name=current.author_name,
            message_type_id=current.message_type_id,
            message_type_name=current.message_type_name,
            subject=current.subject,
            body=current.body,
            status=status,
            created_at=current.created_at,
            updated_at=now,
            sent_at=current.sent_at,
            seen_at=seen_at,
            in_resolution_at=in_resolution_at,
            finished_at=finished_at,
            parent_message_id=current.parent_message_id,
            topic_id=current.topic_id,
            attachments=current.attachments,
            replies=current.replies,
            status_events=current.status_events,
        )
        self._repository.save_message(updated)
        self._repository.add_status_event(
            MessageStatusEventRecord(
                id=str(uuid4()),
                message_id=current.id,
                status=status,
                occurred_at=now,
            ),
        )
        return self.get(current.id)

    def _normalize_attachments(
        self,
        attachments: list[dict[str, str]] | None,
    ) -> list[MessageAttachmentRecord]:
        items: list[MessageAttachmentRecord] = []
        for raw in attachments or []:
            kind = (raw.get("kind") or "").strip()
            name = (raw.get("name") or "").strip()
            url = (raw.get("url") or "").strip()
            if kind not in ATTACHMENT_KINDS or not name or not url:
                continue
            items.append(
                MessageAttachmentRecord(id=str(uuid4()), kind=kind, name=name, url=url),
            )
        return items
