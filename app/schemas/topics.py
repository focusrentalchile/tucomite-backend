"""Schemas for topics and votes. Status is assigned by the server."""

from typing import Literal

from pydantic import BaseModel, Field


class TopicAttachmentPayload(BaseModel):
    """One image, video, or file preview for a topic."""

    kind: Literal["image", "video", "file"]
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1)


class CreateTopicRequest(BaseModel):
    """Fields collected by the new-topic form. Status is not accepted from the client."""

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=500)
    category_key: str = Field(min_length=1, max_length=64)
    attachment_name: str = Field(default="", max_length=255)
    decision: str = Field(min_length=1, max_length=500)
    priority_id: int = Field(ge=1, le=3)
    attachments: list[TopicAttachmentPayload] = []


class UpdateTopicRequest(BaseModel):
    """Editable topic fields. Status is changed with the move endpoint."""

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=500)
    category_key: str = Field(min_length=1, max_length=64)
    attachment_name: str = Field(default="", max_length=255)
    decision: str = Field(min_length=1, max_length=500)
    priority_id: int = Field(ge=1, le=3)
    attachments: list[TopicAttachmentPayload] = []


class MoveTopicRequest(BaseModel):
    """Board column for one topic. Moving to execution requires assignee and dates."""

    status_id: int = Field(ge=1, le=4)
    assignee_user_id: str | None = Field(default=None, max_length=36)
    start_date: str | None = Field(default=None, max_length=10)
    due_date: str | None = Field(default=None, max_length=10)


class CastVoteRequest(BaseModel):
    """Yes, no, or abstain on the topic decision."""

    choice: Literal["yes", "no", "abstain"]


class UpsertOpinionRequest(BaseModel):
    """Written opinion body for one topic."""

    body: str = Field(min_length=1, max_length=500)


class SubmitCompletionRequest(BaseModel):
    """Solution note and evidence when execution work is finished."""

    note: str = Field(min_length=1, max_length=500)
    attachments: list[TopicAttachmentPayload] = []


class TopicVoteResponse(BaseModel):
    """One stored vote."""

    id: str
    author_id: str
    author_name: str
    choice: Literal["yes", "no", "abstain"]


class TopicOpinionResponse(BaseModel):
    """One stored opinion."""

    id: str
    author_id: str
    author_name: str
    body: str
    created_at: str


class TopicConfirmationResponse(BaseModel):
    """One stored completion confirmation."""

    id: str
    author_id: str
    author_name: str
    created_at: str


class TopicAttachmentResponse(BaseModel):
    """One stored attachment preview."""

    id: str
    kind: Literal["image", "video", "file"]
    name: str
    url: str


class TopicResponse(BaseModel):
    """A stored topic, including status, priority, votes, and opinions."""

    id: str
    title: str
    description: str
    category_key: str
    attachment_name: str
    decision: str
    status_id: int
    priority_id: int
    assignee_user_id: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    votes: list[TopicVoteResponse]
    opinions: list[TopicOpinionResponse] = []
    attachments: list[TopicAttachmentResponse] = []
    completion_note: str | None = None
    completion_submitted_at: str | None = None
    completion_attachments: list[TopicAttachmentResponse] = []
    confirmations: list[TopicConfirmationResponse] = []


class TopicListResponse(BaseModel):
    """Topics currently stored."""

    items: list[TopicResponse]


class CastVoteResponse(BaseModel):
    """The saved vote and the topic status after voting."""

    topic_id: str
    status_id: int
    vote: TopicVoteResponse


class UpsertOpinionResponse(BaseModel):
    """The saved opinion for one topic."""

    topic_id: str
    opinion: TopicOpinionResponse


class SubmitCompletionResponse(BaseModel):
    """The topic after completion evidence was stored."""

    topic: TopicResponse


class ConfirmCompletionResponse(BaseModel):
    """The saved confirmation and topic id."""

    topic_id: str
    confirmation: TopicConfirmationResponse
