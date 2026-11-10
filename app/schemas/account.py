"""Schemas for closing a building owner's account."""

from pydantic import BaseModel, Field


class CloseAccountRequest(BaseModel):
    """Why the owner leaves, plus their password as confirmation."""

    reason: str = Field(min_length=1, max_length=2000)
    password: str = Field(min_length=1, max_length=255)
