"""Schemas for committee membership."""

from pydantic import BaseModel, Field


class AddCommitteeMemberRequest(BaseModel):
    """User chosen for the committee."""

    user_id: str = Field(min_length=1, max_length=36)


class CommitteeMemberResponse(BaseModel):
    """One stored committee member."""

    user_id: str
    full_name: str
    email: str


class CommitteeMemberListResponse(BaseModel):
    """Committee members currently stored."""

    items: list[CommitteeMemberResponse]
