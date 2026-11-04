"""Persistence for resident messages and message types."""

from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.messages import (
    DEFAULT_MESSAGE_TYPE_NAMES,
    MessageAttachmentRecord,
    MessageParticipantRecord,
    MessageRecord,
    MessageReplyRecord,
    MessageStatusEventRecord,
    MessageTypeRecord,
)
from app.models.access import UserModel
from app.models.messages import (
    MessageTypeModel,
    ResidentMessageAttachmentModel,
    ResidentMessageModel,
    ResidentMessageParticipantModel,
    ResidentMessageReplyModel,
    ResidentMessageStatusEventModel,
)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.isoformat()


class MessageRepository(Protocol):
    """Persistence port for resident messages."""

    def ensure_default_types(self) -> None: ...

    def list_types(self) -> list[MessageTypeRecord]: ...

    def get_type(self, type_id: str) -> MessageTypeRecord | None: ...

    def list_messages_for_author(self, author_user_id: str) -> list[MessageRecord]: ...

    def list_messages_for_viewer(self, user_id: str) -> list[MessageRecord]: ...

    def list_messages_for_client(self, client_id: str) -> list[MessageRecord]: ...

    def get_message(self, message_id: str) -> MessageRecord | None: ...

    def add_message(self, record: MessageRecord) -> None: ...

    def save_message(self, record: MessageRecord) -> None: ...

    def delete_message(self, message_id: str) -> None: ...

    def replace_message_attachments(
        self,
        message_id: str,
        attachments: list[MessageAttachmentRecord],
    ) -> None: ...

    def replace_participants(self, message_id: str, user_ids: list[str]) -> None: ...

    def add_reply(self, reply: MessageReplyRecord) -> None: ...

    def add_status_event(self, event: MessageStatusEventRecord) -> None: ...


class SqlMessageRepository:
    """SQLAlchemy adapter for resident messages."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_default_types(self) -> None:
        existing = {row.name for row in self._session.scalars(select(MessageTypeModel)).all()}
        for name in DEFAULT_MESSAGE_TYPE_NAMES:
            if name in existing:
                continue
            self._session.add(MessageTypeModel(id=str(uuid4()), name=name))
        self._session.flush()

    def list_types(self) -> list[MessageTypeRecord]:
        self.ensure_default_types()
        rows = self._session.scalars(select(MessageTypeModel).order_by(MessageTypeModel.name)).all()
        return [MessageTypeRecord(id=row.id, name=row.name) for row in rows]

    def get_type(self, type_id: str) -> MessageTypeRecord | None:
        row = self._session.get(MessageTypeModel, type_id)
        if row is None:
            return None
        return MessageTypeRecord(id=row.id, name=row.name)

    def list_messages_for_author(self, author_user_id: str) -> list[MessageRecord]:
        rows = self._session.scalars(
            select(ResidentMessageModel)
            .where(ResidentMessageModel.author_user_id == author_user_id)
            .order_by(ResidentMessageModel.created_at.desc()),
        ).all()
        return [self._message(row) for row in rows]

    def list_messages_for_viewer(self, user_id: str) -> list[MessageRecord]:
        """Messages the person authored or was invited to follow."""
        authored = self._session.scalars(
            select(ResidentMessageModel)
            .where(ResidentMessageModel.author_user_id == user_id)
            .order_by(ResidentMessageModel.created_at.desc()),
        ).all()
        participant_ids = {
            row.message_id
            for row in self._session.scalars(
                select(ResidentMessageParticipantModel).where(
                    ResidentMessageParticipantModel.user_id == user_id,
                ),
            ).all()
        }
        participated: list[ResidentMessageModel] = []
        if participant_ids:
            participated = list(
                self._session.scalars(
                    select(ResidentMessageModel)
                    .where(ResidentMessageModel.id.in_(participant_ids))
                    .order_by(ResidentMessageModel.created_at.desc()),
                ).all(),
            )
        by_id: dict[str, ResidentMessageModel] = {row.id: row for row in authored}
        for row in participated:
            by_id.setdefault(row.id, row)
        ordered = sorted(
            by_id.values(),
            key=lambda row: row.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return [self._message(row) for row in ordered]

    def list_messages_for_client(self, client_id: str) -> list[MessageRecord]:
        rows = self._session.scalars(
            select(ResidentMessageModel)
            .where(ResidentMessageModel.client_id == client_id)
            .order_by(ResidentMessageModel.created_at.desc()),
        ).all()
        return [self._message(row) for row in rows]

    def get_message(self, message_id: str) -> MessageRecord | None:
        row = self._session.get(ResidentMessageModel, message_id)
        if row is None:
            return None
        return self._message(row)

    def add_message(self, record: MessageRecord) -> None:
        self._session.add(
            ResidentMessageModel(
                id=record.id,
                client_id=record.client_id,
                author_user_id=record.author_user_id,
                message_type_id=record.message_type_id,
                subject=record.subject,
                body=record.body,
                status=record.status,
                parent_message_id=record.parent_message_id,
                topic_id=record.topic_id,
                sent_at=datetime.fromisoformat(record.sent_at.replace("Z", "+00:00")),
            ),
        )
        self._session.flush()
        self.replace_message_attachments(record.id, list(record.attachments))
        self.replace_participants(record.id, [item.user_id for item in record.participants])
        for event in record.status_events:
            self.add_status_event(event)

    def save_message(self, record: MessageRecord) -> None:
        row = self._session.get(ResidentMessageModel, record.id)
        if row is None:
            return
        row.message_type_id = record.message_type_id
        row.subject = record.subject
        row.body = record.body
        row.status = record.status
        row.parent_message_id = record.parent_message_id
        row.topic_id = record.topic_id
        row.seen_at = (
            datetime.fromisoformat(record.seen_at.replace("Z", "+00:00")) if record.seen_at else None
        )
        row.in_resolution_at = (
            datetime.fromisoformat(record.in_resolution_at.replace("Z", "+00:00"))
            if record.in_resolution_at
            else None
        )
        row.finished_at = (
            datetime.fromisoformat(record.finished_at.replace("Z", "+00:00"))
            if record.finished_at
            else None
        )
        self._session.flush()

    def delete_message(self, message_id: str) -> None:
        self._session.execute(
            delete(ResidentMessageParticipantModel).where(
                ResidentMessageParticipantModel.message_id == message_id,
            ),
        )
        self._session.execute(
            delete(ResidentMessageAttachmentModel).where(
                ResidentMessageAttachmentModel.message_id == message_id,
            ),
        )
        reply_ids = [
            row.id
            for row in self._session.scalars(
                select(ResidentMessageReplyModel).where(ResidentMessageReplyModel.message_id == message_id),
            ).all()
        ]
        if reply_ids:
            self._session.execute(
                delete(ResidentMessageAttachmentModel).where(
                    ResidentMessageAttachmentModel.reply_id.in_(reply_ids),
                ),
            )
        self._session.execute(
            delete(ResidentMessageReplyModel).where(ResidentMessageReplyModel.message_id == message_id),
        )
        self._session.execute(
            delete(ResidentMessageStatusEventModel).where(
                ResidentMessageStatusEventModel.message_id == message_id,
            ),
        )
        row = self._session.get(ResidentMessageModel, message_id)
        if row is not None:
            self._session.delete(row)
        self._session.flush()

    def replace_message_attachments(
        self,
        message_id: str,
        attachments: list[MessageAttachmentRecord],
    ) -> None:
        self._session.execute(
            delete(ResidentMessageAttachmentModel).where(
                ResidentMessageAttachmentModel.message_id == message_id,
                ResidentMessageAttachmentModel.reply_id.is_(None),
            ),
        )
        for item in attachments:
            self._session.add(
                ResidentMessageAttachmentModel(
                    id=item.id,
                    message_id=message_id,
                    reply_id=None,
                    kind=item.kind,
                    name=item.name,
                    url=item.url,
                ),
            )
        self._session.flush()

    def replace_participants(self, message_id: str, user_ids: list[str]) -> None:
        self._session.execute(
            delete(ResidentMessageParticipantModel).where(
                ResidentMessageParticipantModel.message_id == message_id,
            ),
        )
        seen: set[str] = set()
        for user_id in user_ids:
            cleaned = user_id.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            self._session.add(
                ResidentMessageParticipantModel(message_id=message_id, user_id=cleaned),
            )
        self._session.flush()

    def add_reply(self, reply: MessageReplyRecord) -> None:
        self._session.add(
            ResidentMessageReplyModel(
                id=reply.id,
                message_id=reply.message_id,
                author_user_id=reply.author_user_id,
                body=reply.body,
                from_admin=reply.from_admin,
                created_at=datetime.fromisoformat(reply.created_at.replace("Z", "+00:00")),
            ),
        )
        for item in reply.attachments:
            self._session.add(
                ResidentMessageAttachmentModel(
                    id=item.id,
                    message_id=None,
                    reply_id=reply.id,
                    kind=item.kind,
                    name=item.name,
                    url=item.url,
                ),
            )
        self._session.flush()

    def add_status_event(self, event: MessageStatusEventRecord) -> None:
        self._session.add(
            ResidentMessageStatusEventModel(
                id=event.id,
                message_id=event.message_id,
                status=event.status,
                occurred_at=datetime.fromisoformat(event.occurred_at.replace("Z", "+00:00")),
            ),
        )
        self._session.flush()

    def _message(self, row: ResidentMessageModel) -> MessageRecord:
        type_row = self._session.get(MessageTypeModel, row.message_type_id)
        author = self._session.get(UserModel, row.author_user_id)
        attachments = [
            MessageAttachmentRecord(id=item.id, kind=item.kind, name=item.name, url=item.url)
            for item in self._session.scalars(
                select(ResidentMessageAttachmentModel).where(
                    ResidentMessageAttachmentModel.message_id == row.id,
                    ResidentMessageAttachmentModel.reply_id.is_(None),
                ),
            ).all()
        ]
        replies: list[MessageReplyRecord] = []
        for reply_row in self._session.scalars(
            select(ResidentMessageReplyModel)
            .where(ResidentMessageReplyModel.message_id == row.id)
            .order_by(ResidentMessageReplyModel.created_at.asc()),
        ).all():
            reply_author = self._session.get(UserModel, reply_row.author_user_id)
            reply_attachments = [
                MessageAttachmentRecord(id=item.id, kind=item.kind, name=item.name, url=item.url)
                for item in self._session.scalars(
                    select(ResidentMessageAttachmentModel).where(
                        ResidentMessageAttachmentModel.reply_id == reply_row.id,
                    ),
                ).all()
            ]
            replies.append(
                MessageReplyRecord(
                    id=reply_row.id,
                    message_id=reply_row.message_id,
                    author_user_id=reply_row.author_user_id,
                    author_name=reply_author.full_name if reply_author else "",
                    body=reply_row.body,
                    from_admin=reply_row.from_admin,
                    created_at=_iso(reply_row.created_at) or "",
                    attachments=tuple(reply_attachments),
                ),
            )
        events = [
            MessageStatusEventRecord(
                id=item.id,
                message_id=item.message_id,
                status=item.status,
                occurred_at=_iso(item.occurred_at) or "",
            )
            for item in self._session.scalars(
                select(ResidentMessageStatusEventModel)
                .where(ResidentMessageStatusEventModel.message_id == row.id)
                .order_by(ResidentMessageStatusEventModel.occurred_at.asc()),
            ).all()
        ]
        participants: list[MessageParticipantRecord] = []
        for link in self._session.scalars(
            select(ResidentMessageParticipantModel).where(
                ResidentMessageParticipantModel.message_id == row.id,
            ),
        ).all():
            person = self._session.get(UserModel, link.user_id)
            participants.append(
                MessageParticipantRecord(
                    user_id=link.user_id,
                    full_name=person.full_name if person else "",
                    email=person.email if person else "",
                ),
            )
        participants.sort(key=lambda item: item.full_name.casefold())
        return MessageRecord(
            id=row.id,
            client_id=row.client_id,
            author_user_id=row.author_user_id,
            author_name=author.full_name if author else "",
            message_type_id=row.message_type_id,
            message_type_name=type_row.name if type_row else "",
            subject=row.subject,
            body=row.body,
            status=row.status,
            created_at=_iso(row.created_at) or "",
            updated_at=_iso(row.updated_at) or "",
            sent_at=_iso(row.sent_at) or "",
            seen_at=_iso(row.seen_at),
            in_resolution_at=_iso(row.in_resolution_at),
            finished_at=_iso(row.finished_at),
            parent_message_id=row.parent_message_id,
            topic_id=row.topic_id,
            attachments=tuple(attachments),
            replies=tuple(replies),
            status_events=tuple(events),
            participants=tuple(participants),
        )
