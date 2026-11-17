"""Schemas for topics and votes. Status is assigned by the server."""

from typing import Literal

from pydantic import BaseModel, Field


class TopicAttachmentPayload(BaseModel):
    """One image, video, or file preview for a topic."""

    kind: Literal["image", "video", "file"]
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1)


class TopicVoteOptionPayload(BaseModel):
    """One custom answer option label (id is assigned by the server when omitted)."""

    id: str | None = Field(default=None, max_length=36)
    label: str = Field(min_length=1, max_length=120)


class CreateTopicRequest(BaseModel):
    """Fields collected by the new-topic form. Status is not accepted from the client."""

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=500)
    category_key: str = Field(min_length=1, max_length=64)
    attachment_name: str = Field(default="", max_length=255)
    decision: str = Field(min_length=1, max_length=500)
    priority_id: int = Field(ge=1, le=3)
    vote_type: Literal["yes_no", "custom"] = "yes_no"
    vote_options: list[TopicVoteOptionPayload] = []
    attachments: list[TopicAttachmentPayload] = []
    voting_starts_at: str | None = Field(default=None, max_length=40)
    voting_ends_at: str | None = Field(default=None, max_length=40)


class UpdateTopicRequest(BaseModel):
    """Editable topic fields. Status is changed with the move endpoint."""

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=500)
    category_key: str = Field(min_length=1, max_length=64)
    attachment_name: str = Field(default="", max_length=255)
    decision: str = Field(min_length=1, max_length=500)
    priority_id: int = Field(ge=1, le=3)
    vote_type: Literal["yes_no", "custom"] = "yes_no"
    vote_options: list[TopicVoteOptionPayload] = []
    attachments: list[TopicAttachmentPayload] = []


class MoveTopicRequest(BaseModel):
    """Board column for one topic. Moving to execution requires assignee and dates."""

    status_id: int = Field(ge=1, le=4)
    assignee_user_id: str | None = Field(default=None, max_length=36)
    start_date: str | None = Field(default=None, max_length=10)
    due_date: str | None = Field(default=None, max_length=10)


class CastVoteRequest(BaseModel):
    """Yes/no/abstain, or a custom option id for multi-choice polls."""

    choice: str = Field(min_length=1, max_length=36)


class UpsertOpinionRequest(BaseModel):
    """Written opinion body for one topic."""

    body: str = Field(min_length=1, max_length=500)


class SubmitCompletionRequest(BaseModel):
    """Solution note and evidence when execution work is finished."""

    note: str = Field(min_length=1, max_length=500)
    attachments: list[TopicAttachmentPayload] = []


class ConfirmCompletionRequest(BaseModel):
    """Committee Resultado vote: was the topic resolved?"""

    choice: Literal["yes", "no"]
    reason: str | None = Field(default=None, max_length=500)


class TopicVoteOptionResponse(BaseModel):
    """One stored custom poll option."""

    id: str
    label: str


class TopicVoteResponse(BaseModel):
    """One stored vote."""

    id: str
    author_id: str
    author_name: str
    choice: str


class TopicOpinionResponse(BaseModel):
    """One stored opinion."""

    id: str
    author_id: str
    author_name: str
    body: str
    created_at: str


class TopicConfirmationResponse(BaseModel):
    """One stored Resultado vote."""

    id: str
    author_id: str
    author_name: str
    created_at: str
    choice: Literal["yes", "no"] = "yes"
    reason: str | None = None


class TopicAttachmentResponse(BaseModel):
    """One stored attachment preview."""

    id: str
    kind: Literal["image", "video", "file"]
    name: str
    url: str


class TopicCompletionRoundResponse(BaseModel):
    """One sealed Resultado attempt (failed or passed)."""

    round_number: int
    note: str
    submitted_at: str
    closed_at: str
    outcome: Literal["failed", "passed"]
    confirmations: list[TopicConfirmationResponse] = []
    attachments: list[TopicAttachmentResponse] = []


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
    assignee_role_key: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    vote_type: Literal["yes_no", "custom"] = "yes_no"
    vote_options: list[TopicVoteOptionResponse] = []
    client_id: str | None = None
    voting_starts_at: str | None = None
    voting_ends_at: str | None = None
    status_entered_at: str | None = None
    votes: list[TopicVoteResponse]
    opinions: list[TopicOpinionResponse] = []
    attachments: list[TopicAttachmentResponse] = []
    completion_note: str | None = None
    completion_submitted_at: str | None = None
    completion_round: int = 1
    completion_rounds: list[TopicCompletionRoundResponse] = []
    completion_attachments: list[TopicAttachmentResponse] = []
    confirmations: list[TopicConfirmationResponse] = []
    # Per-actor fields filled by GET /topics.
    unread_opinion_count: int = 0
    opinions_last_seen_at: str | None = None
    # Waiting column, vote majority met, and nobody assigned yet.
    assign_ready: bool = False
    has_assign_ready_alert: bool = False
    # Waiting + voting ended without majority (standby / debate in Opiniones).
    no_consensus: bool = False
    # voting_ends_at + 5 days (ISO), when the consensus grace window closes.
    consensus_ends_at: str | None = None


class TopicListResponse(BaseModel):
    """Topics currently stored."""

    items: list[TopicResponse]


class CastVoteResponse(BaseModel):
    """The saved vote and the topic status after voting."""

    topic_id: str
    status_id: int
    vote: TopicVoteResponse


class UpsertOpinionResponse(BaseModel):
    """One newly appended opinion on a topic."""

    topic_id: str
    opinion: TopicOpinionResponse


class SeenOpinionsResponse(BaseModel):
    """Instant stored when the actor opened the opinions of a topic."""

    topic_id: str
    last_seen_at: str


class SubmitCompletionResponse(BaseModel):
    """The topic after completion evidence was stored."""

    topic: TopicResponse


class ConfirmCompletionResponse(BaseModel):
    """The saved confirmation and refreshed topic (may clear after No majority)."""

    topic_id: str
    confirmation: TopicConfirmationResponse
    topic: TopicResponse | None = None
