"""HTTP schemas for public contact messages."""

from pydantic import BaseModel, Field


class CreateContactMessageRequest(BaseModel):
    """Fields submitted from the public contact form."""

    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=255)
    subject: str = Field(default="", max_length=200)
    message: str = Field(min_length=1, max_length=5000)
    privacy_accepted: bool


class ContactMessageResponse(BaseModel):
    """One contact message returned to the super admin."""

    id: str
    name: str
    email: str
    subject: str = ""
    message: str
    privacy_accepted: bool
    privacy_accepted_at: str | None
    created_at: str


class ContactMessageListResponse(BaseModel):
    """Contact message collection."""

    items: list[ContactMessageResponse]
