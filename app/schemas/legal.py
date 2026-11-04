"""HTTP schemas for legal cases."""

from typing import Literal

from pydantic import BaseModel, Field

LegalStatus = Literal["waiting", "in_progress", "finished"]


class LegalCaseAttachmentPayload(BaseModel):
    """Attachment uploaded with a legal case."""

    kind: Literal["image", "video", "file"] = "file"
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1)


class CreateLegalCaseRequest(BaseModel):
    """Body to open a new legal case."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    attachments: list[LegalCaseAttachmentPayload] = Field(default_factory=list)


class UpdateLegalCaseRequest(BaseModel):
    """Body to update an existing legal case."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    attachments: list[LegalCaseAttachmentPayload] = Field(default_factory=list)


class SetLegalCaseStatusRequest(BaseModel):
    """Body to move a case on the counsel board."""

    status: LegalStatus


class CreateLegalCaseMessageRequest(BaseModel):
    """Body to post a message on a legal case."""

    body: str = Field(min_length=1)


class LegalCaseAttachmentResponse(BaseModel):
    """One attachment on a legal case."""

    id: str
    kind: Literal["image", "video", "file"]
    name: str
    url: str


class LegalCaseMessageResponse(BaseModel):
    """One message on a legal case thread."""

    id: str
    author_user_id: str
    author_name: str
    body: str
    from_legal: bool
    created_at: str


class LegalCaseResponse(BaseModel):
    """One legal case with its attachments and optional messages."""

    id: str
    title: str
    description: str
    status: LegalStatus
    created_at: str
    attachments: list[LegalCaseAttachmentResponse] = Field(default_factory=list)
    messages: list[LegalCaseMessageResponse] = Field(default_factory=list)


class LegalCaseListResponse(BaseModel):
    """List of legal cases for the building."""

    items: list[LegalCaseResponse]
