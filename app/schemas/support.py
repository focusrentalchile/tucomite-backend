"""HTTP schemas for support tickets and Gestión workspace imports."""

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
    client_id: str | None = Field(default=None, max_length=36)


class CreateSupportMessageRequest(BaseModel):
    """Reply inside a ticket."""

    body: str = Field(min_length=1, max_length=5000)


class UpdateSupportTicketStatusRequest(BaseModel):
    """Move a ticket across board columns."""

    status: str = Field(min_length=1, max_length=32)


class SupportWorkspaceClientResponse(BaseModel):
    """One building on the Gestión workspace."""

    client_id: str
    client_name: str
    home: bool


class SupportWorkspaceClientListResponse(BaseModel):
    """Workspace buildings for the signed-in administrator."""

    items: list[SupportWorkspaceClientResponse]


class SupportWorkspaceImportResponse(BaseModel):
    """Permission request to import a building into Gestión."""

    id: str
    administrator_user_id: str
    administrator_name: str
    administrator_email: str
    client_id: str
    client_name: str
    status: str
    created_at: str
    resolved_at: str | None = None


class SupportWorkspaceImportListResponse(BaseModel):
    """Import request collection."""

    items: list[SupportWorkspaceImportResponse]


class CreateSupportWorkspaceImportRequest(BaseModel):
    """Ask a building owner (by email) to approve Gestión access."""

    owner_email: str = Field(min_length=3, max_length=255)
