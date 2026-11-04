"""HTTP schemas for resident messages."""

from pydantic import BaseModel, Field


class MessageAttachmentPayload(BaseModel):
    """One attachment in a create/update/reply body."""

    kind: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1)


class MessageAttachmentResponse(BaseModel):
    """Stored attachment."""

    id: str
    kind: str
    name: str
    url: str


class MessageTypeResponse(BaseModel):
    """One message type for selects."""

    id: str
    name: str


class MessageTypeListResponse(BaseModel):
    """Alphabetical message types."""

    items: list[MessageTypeResponse]


class MessageReplyResponse(BaseModel):
    """One reply on a message."""

    id: str
    message_id: str
    author_user_id: str
    author_name: str
    body: str
    from_admin: bool
    created_at: str
    attachments: list[MessageAttachmentResponse] = []


class MessageStatusEventResponse(BaseModel):
    """One status change timestamp."""

    id: str
    message_id: str
    status: str
    occurred_at: str


class MessageParticipantResponse(BaseModel):
    """One invited resident on a message."""

    user_id: str
    full_name: str
    email: str = ""


class MessageResponse(BaseModel):
    """Full message ticket."""

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
    attachments: list[MessageAttachmentResponse] = []
    replies: list[MessageReplyResponse] = []
    status_events: list[MessageStatusEventResponse] = []
    participants: list[MessageParticipantResponse] = []


class MessageListResponse(BaseModel):
    """List of message tickets."""

    items: list[MessageResponse]


class MessageParticipantCandidateResponse(BaseModel):
    """Resident that can be invited onto a message."""

    id: str
    full_name: str
    email: str


class MessageParticipantCandidateListResponse(BaseModel):
    """Other residents in the building."""

    items: list[MessageParticipantCandidateResponse]


class CreateMessageRequest(BaseModel):
    """Resident creates a message."""

    message_type_id: str = Field(min_length=1, max_length=36)
    subject: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1)
    attachments: list[MessageAttachmentPayload] = []
    participant_user_ids: list[str] = []


class UpdateMessageRequest(BaseModel):
    """Resident edits a still-sent message."""

    message_type_id: str = Field(min_length=1, max_length=36)
    subject: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1)
    attachments: list[MessageAttachmentPayload] = []
    participant_user_ids: list[str] = []


class CreateMessageReplyRequest(BaseModel):
    """Admin or resident posts a reply."""

    body: str = Field(min_length=1)
    attachments: list[MessageAttachmentPayload] = []


class UpdateMessageStatusRequest(BaseModel):
    """Administrator moves a message column."""

    status: str = Field(min_length=1, max_length=32)


class AppealMessageRequest(BaseModel):
    """Resident appeals a finished message."""

    body: str = Field(min_length=1)
    attachments: list[MessageAttachmentPayload] = []
