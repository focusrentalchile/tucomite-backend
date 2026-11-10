"""HTTP schemas for management tasks and Gestión workspace imports."""

from typing import Literal

from pydantic import BaseModel, Field


class ManagementAttachmentPayload(BaseModel):
    """One image, video, or file sent with a task or a reply (url may be a data URL)."""

    kind: Literal["image", "video", "file"]
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1)


class ManagementAttachmentResponse(BaseModel):
    """One stored attachment."""

    id: str
    kind: Literal["image", "video", "file"]
    name: str
    url: str


class ManagementMessageResponse(BaseModel):
    """One message in a ticket thread."""

    id: str
    author_user_id: str
    author_name: str
    body: str
    created_at: str
    from_staff: bool
    attachments: list[ManagementAttachmentResponse] = []


class ManagementTaskResponse(BaseModel):
    """A management task, optionally with its messages."""

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
    messages: list[ManagementMessageResponse] = []
    attachments: list[ManagementAttachmentResponse] = []


class ManagementTaskListResponse(BaseModel):
    """Ticket collection."""

    items: list[ManagementTaskResponse]


class CreateManagementTaskRequest(BaseModel):
    """Open a new management task in Pendientes."""

    subject: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=5000)
    priority_id: int = Field(default=2, ge=1, le=3)
    due_date: str | None = Field(default=None, max_length=10)
    client_id: str | None = Field(default=None, max_length=36)
    attachments: list[ManagementAttachmentPayload] = []


class CreateManagementMessageRequest(BaseModel):
    """Reply inside a ticket."""

    body: str = Field(min_length=1, max_length=5000)
    attachments: list[ManagementAttachmentPayload] = []


class UpdateManagementTaskStatusRequest(BaseModel):
    """Move a ticket across board columns."""

    status: str = Field(min_length=1, max_length=32)


class ManagementWorkspaceClientResponse(BaseModel):
    """One building on the Gestión workspace."""

    client_id: str
    client_name: str
    home: bool


class ManagementWorkspaceClientListResponse(BaseModel):
    """Workspace buildings for the signed-in administrator."""

    items: list[ManagementWorkspaceClientResponse]


class ManagementWorkspaceImportResponse(BaseModel):
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


class ManagementWorkspaceImportListResponse(BaseModel):
    """Import request collection."""

    items: list[ManagementWorkspaceImportResponse]


class CreateManagementWorkspaceImportRequest(BaseModel):
    """Ask a building owner (by email) to approve Gestión access."""

    owner_email: str = Field(min_length=3, max_length=255)


class BuildingAdministratorResponse(BaseModel):
    """Administrator history row on the Administración screen."""

    user_id: str
    full_name: str
    email: str
    home: bool
    import_id: str | None = None
    status: str
    created_at: str = ""
    resolved_at: str | None = None


class BuildingAdministratorListResponse(BaseModel):
    """Administrators visible on the Administración screen."""

    items: list[BuildingAdministratorResponse]
