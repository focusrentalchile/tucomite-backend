"""HTTP schemas for platform clients."""

from pydantic import BaseModel, Field


class ClientResponse(BaseModel):
    """One client and the email of its administrator."""

    id: str
    name: str
    admin_user_id: str
    admin_email: str


class ClientListResponse(BaseModel):
    """Client collection."""

    items: list[ClientResponse]


class CreateClientRequest(BaseModel):
    """Fields to create a client and its administrator."""

    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)
