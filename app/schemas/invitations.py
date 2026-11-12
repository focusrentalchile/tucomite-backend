"""HTTP schemas for invitations."""

from pydantic import BaseModel, Field


class CreatePlatformInvitationRequest(BaseModel):
    """Super-admin invite: responsible name + email only."""

    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=255)


class CreateBuildingInvitationRequest(BaseModel):
    """Building-owner invite: name, email, and role key."""

    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=255)
    role_key: str = Field(min_length=1, max_length=64)


class AcceptPlatformInvitationRequest(BaseModel):
    """Public registration payload for a platform invitation token."""

    building_name: str = Field(min_length=1, max_length=160)
    address: str = Field(default="", max_length=255)
    password: str = Field(min_length=6, max_length=128)


class AcceptBuildingInvitationRequest(BaseModel):
    """Public registration payload for a building invitation token."""

    password: str = Field(min_length=6, max_length=128)
    floor_number: str = Field(default="", max_length=32)
    apartment_number: str = Field(default="", max_length=32)


class InvitationResponse(BaseModel):
    """One invitation for the admin table."""

    id: str
    kind: str
    name: str
    email: str
    building_name: str
    role_key: str
    client_id: str | None
    status: str
    sent_at: str | None
    opened_at: str | None
    registered_at: str | None
    created_at: str


class InvitationListResponse(BaseModel):
    """Invitation collection."""

    items: list[InvitationResponse]


class PublicInvitationResponse(BaseModel):
    """Public fields needed to render the register form."""

    kind: str
    name: str
    email: str
    building_name: str
    role_key: str
    status: str
