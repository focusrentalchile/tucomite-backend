"""Domain records for resident building messages."""

from dataclasses import dataclass

MESSAGE_STATUS_SENT = "sent"
MESSAGE_STATUS_SEEN = "seen"
MESSAGE_STATUS_IN_RESOLUTION = "in_resolution"
MESSAGE_STATUS_FINISHED = "finished"

MESSAGE_STATUSES = frozenset(
    {
        MESSAGE_STATUS_SENT,
        MESSAGE_STATUS_SEEN,
        MESSAGE_STATUS_IN_RESOLUTION,
        MESSAGE_STATUS_FINISHED,
    }
)

ATTACHMENT_KINDS = frozenset({"image", "video", "file"})

DEFAULT_MESSAGE_TYPE_NAMES = ("Consulta", "Incidencia")


@dataclass(frozen=True)
class MessageTypeRecord:
    """One selectable message type."""

    id: str
    name: str


@dataclass(frozen=True)
class MessageAttachmentRecord:
    """One image, video, or file on a message or reply."""

    id: str
    kind: str
    name: str
    url: str


@dataclass(frozen=True)
class MessageReplyRecord:
    """One reply on a resident message thread."""

    id: str
    message_id: str
    author_user_id: str
    author_name: str
    body: str
    from_admin: bool
    created_at: str
    attachments: tuple[MessageAttachmentRecord, ...] = ()


@dataclass(frozen=True)
class MessageStatusEventRecord:
    """One status transition with second-precision timestamp."""

    id: str
    message_id: str
    status: str
    occurred_at: str


@dataclass(frozen=True)
class MessageParticipantRecord:
    """One other resident invited to follow a message."""

    user_id: str
    full_name: str
    email: str = ""


@dataclass(frozen=True)
class MessageRecord:
    """One resident message ticket for a building."""

    id: str
    client_id: str
    author_user_id: str
    author_name: str
    message_type_id: str
    message_type_name: str
    subject: str
    body: str
    status: str
    created_at: str
    updated_at: str
    sent_at: str
    seen_at: str | None = None
    in_resolution_at: str | None = None
    finished_at: str | None = None
    parent_message_id: str | None = None
    topic_id: str | None = None
    attachments: tuple[MessageAttachmentRecord, ...] = ()
    replies: tuple[MessageReplyRecord, ...] = ()
    status_events: tuple[MessageStatusEventRecord, ...] = ()
    participants: tuple[MessageParticipantRecord, ...] = ()


class MessageNotFound(Exception):
    """Raised when a message id does not exist."""


class MessageTypeNotFound(Exception):
    """Raised when a message type id does not exist."""


class InvalidMessageStatus(Exception):
    """Raised when a status transition is not allowed."""
