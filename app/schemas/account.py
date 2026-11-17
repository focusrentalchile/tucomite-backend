"""Schemas for closing a building owner's account."""

from pydantic import BaseModel, Field


class CloseAccountRequest(BaseModel):
    """Why the owner leaves, plus their password as confirmation."""

    reason: str = Field(min_length=1, max_length=2000)
    password: str = Field(min_length=1, max_length=255)


class UpdateAccountProfileRequest(BaseModel):
    """First and last name for the signed-in building owner."""

    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)


class AccountProfileResponse(BaseModel):
    """Profile fields shown on the Cuenta screen."""

    first_name: str
    last_name: str
    full_name: str
    email: str
