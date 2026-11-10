"""I/O schemas for the building wall and sales feed."""

from pydantic import BaseModel, Field


class BuildingWallPostResponse(BaseModel):
    """One public wall or sales post."""

    id: str
    client_id: str
    author_user_id: str
    author_name: str
    kind: str
    body: str
    title: str | None = None
    price: str | None = None
    image_name: str | None = None
    image_url: str | None = None
    created_at: str


class BuildingWallPostListResponse(BaseModel):
    """List payload for wall or sales posts."""

    items: list[BuildingWallPostResponse]


class CreateBuildingWallPostRequest(BaseModel):
    """Body for creating a wall or sales post."""

    kind: str = Field(min_length=1, max_length=16)
    body: str = Field(default="", max_length=8000)
    title: str | None = Field(default=None, max_length=160)
    price: str | None = Field(default=None, max_length=40)
    image_name: str | None = Field(default=None, max_length=255)
    image_url: str | None = Field(default=None, max_length=5_000_000)
