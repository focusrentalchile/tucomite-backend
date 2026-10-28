"""HTTP schemas for support tickets."""

from pydantic import BaseModel, Field


class SupportMessageResponse(BaseModel):
    """One message in a ticket thread."""

    id: str
    author_user_id: str
    author_name: str
    body: str
    created_at: str
    from_staff: bool


class SupportTicketResponse(BaseModel):
    """A support ticket, optionally with its messages."""

    id: str
    client_id: str | None
    client_name: str
    created_by_user_id: str
    created_by_name: str
    subject: str
    status: str
    priority_id: int
    due_date: str | None = None
    assignee_user_id: str | None = None
    topic_id: str | None = None
    created_at: str
    updated_at: str
    messages: list[SupportMessageResponse] = []


class SupportTicketListResponse(BaseModel):
    """Ticket collection."""

    items: list[SupportTicketResponse]


class CreateSupportTicketRequest(BaseModel):
    """Open a new support ticket in Pendientes."""

    subject: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=5000)
    priority_id: int = Field(default=2, ge=1, le=3)
    due_date: str | None = Field(default=None, max_length=10)


class CreateSupportMessageRequest(BaseModel):
    """Reply inside a ticket."""

    body: str = Field(min_length=1, max_length=5000)


class UpdateSupportTicketStatusRequest(BaseModel):
    """Move a ticket across board columns."""

    status: str = Field(min_length=1, max_length=32)
