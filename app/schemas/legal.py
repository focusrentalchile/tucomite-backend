"""HTTP schemas for legal cases."""

from typing import Literal

from pydantic import BaseModel, Field


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


class LegalCaseAttachmentResponse(BaseModel):
    """One attachment on a legal case."""

    id: str
    kind: Literal["image", "video", "file"]
    name: str
    url: str


class LegalCaseResponse(BaseModel):
    """One legal case with its attachments."""

    id: str
    title: str
    description: str
    created_at: str
    attachments: list[LegalCaseAttachmentResponse] = Field(default_factory=list)


class LegalCaseListResponse(BaseModel):
    """List of legal cases for the building."""

    items: list[LegalCaseResponse]
