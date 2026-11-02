"""Request and response shapes for projects."""

from pydantic import BaseModel, Field


class ProjectAttachmentPayload(BaseModel):
    """One attachment sent when creating or updating a project."""

    kind: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1)


class ProjectAttachmentResponse(BaseModel):
    """One stored project attachment preview."""

    id: str
    kind: str
    name: str
    url: str


class ProjectResponse(BaseModel):
    """One project."""

    id: str
    period_id: str
    title: str
    description: str
    photo_names: str
    created_at: str
    due_date: str | None = None
    attachments: list[ProjectAttachmentResponse] = []


class ProjectListResponse(BaseModel):
    """Project collection."""

    items: list[ProjectResponse]


class CreateProjectRequest(BaseModel):
    """Payload to create a project."""

    period_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    photo_names: str = Field(default="", max_length=1000)
    due_date: str | None = Field(default=None, max_length=10)
    attachments: list[ProjectAttachmentPayload] = []


class UpdateProjectRequest(BaseModel):
    """Payload to update a project."""

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    photo_names: str = Field(default="", max_length=1000)
    due_date: str | None = Field(default=None, max_length=10)
    attachments: list[ProjectAttachmentPayload] = []
