"""Request and response shapes for projects."""

from pydantic import BaseModel, Field


class ProjectResponse(BaseModel):
    """One project."""

    id: str
    period_id: str
    title: str
    description: str
    photo_names: str


class ProjectListResponse(BaseModel):
    """Project collection."""

    items: list[ProjectResponse]


class CreateProjectRequest(BaseModel):
    """Payload to create a project."""

    period_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    photo_names: str = Field(default="", max_length=1000)


class UpdateProjectRequest(BaseModel):
    """Payload to update a project."""

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2000)
    photo_names: str = Field(default="", max_length=1000)
