"""HTTP schemas for platform clients."""

from pydantic import BaseModel, Field


class ClientResponse(BaseModel):
    """One client, its administrator email, and license window."""

    id: str
    name: str
    admin_user_id: str
    admin_email: str
    license_starts_at: str | None = None
    license_ends_at: str | None = None
    license_status: str | None = None


class ClientListResponse(BaseModel):
    """Client collection."""

    items: list[ClientResponse]


class CreateClientRequest(BaseModel):
    """Fields to create a client and its administrator."""

    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    license_starts_at: str = Field(min_length=10, max_length=10)
    license_ends_at: str = Field(min_length=10, max_length=10)


class UpdateClientRequest(BaseModel):
    """Fields to update a client and optionally its administrator credentials."""

    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=255)
    password: str | None = Field(default=None, min_length=6, max_length=128)
    license_starts_at: str = Field(min_length=10, max_length=10)
    license_ends_at: str = Field(min_length=10, max_length=10)
