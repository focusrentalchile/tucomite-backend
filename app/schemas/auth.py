"""HTTP schemas for session sign-in."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Email and password for session sign-in."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)


class LoginResponse(BaseModel):
    """Signed-in person returned after a successful login."""

    id: str
    full_name: str
    email: str
    role_id: str
    is_super_admin: bool
    client_id: str | None
    is_committee_member: bool
