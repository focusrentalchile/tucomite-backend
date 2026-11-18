"""Schemas for closing a building owner's account."""

from pydantic import BaseModel, Field


class CloseAccountRequest(BaseModel):
    """Why the owner leaves, plus their password as confirmation."""

    reason: str = Field(min_length=1, max_length=2000)
    password: str = Field(min_length=1, max_length=255)


class UpdateAccountProfileRequest(BaseModel):
    """Name, identification number, and optional avatar for the signed-in person."""

    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    avatar_url: str = Field(default="", max_length=6_000_000)
    identification_number: str = Field(min_length=3, max_length=20)


class AccountProfileResponse(BaseModel):
    """Profile fields shown on the Cuenta screen."""

    first_name: str
    last_name: str
    full_name: str
    email: str
    avatar_url: str = ""
    identification_number: str = ""
