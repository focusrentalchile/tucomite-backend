"""HTTP schemas for platform support tickets."""

from pydantic import BaseModel, Field


class SupportTypeResponse(BaseModel):
    """One support type for selects."""

    id: str
    name: str


class SupportTypeListResponse(BaseModel):
    """Alphabetical support types."""

    items: list[SupportTypeResponse]


class SupportReplyResponse(BaseModel):
    """One reply on a support ticket."""

    id: str
    ticket_id: str
    author_user_id: str | None
    author_name: str
    body: str
    from_staff: bool
    created_at: str


class SupportTicketResponse(BaseModel):
    """Full support ticket with chat replies."""

    id: str
    client_id: str | None = None
    author_user_id: str | None = None
    author_name: str = ""
    support_type_id: str
    support_type_name: str
    subject: str
    body: str
    status: str
    contact_name: str | None = None
    contact_email: str | None = None
    created_at: str
    updated_at: str
    replies: list[SupportReplyResponse] = []


class SupportTicketListResponse(BaseModel):
    """List of support tickets."""

    items: list[SupportTicketResponse]


class CreateSupportTicketRequest(BaseModel):
    """Body for opening a building support ticket. Type is assigned as Soporte."""

    subject: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=8000)
    support_type_id: str | None = Field(default=None, max_length=36)


class CreateSupportReplyRequest(BaseModel):
    """Body for posting a chat reply."""

    body: str = Field(min_length=1, max_length=8000)
