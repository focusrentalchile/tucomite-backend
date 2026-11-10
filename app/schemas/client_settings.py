"""Schemas for per-building settings."""

from pydantic import BaseModel, Field

from app.domain.client_settings import MAX_VOTE_WINDOW_HOURS, MIN_VOTE_WINDOW_HOURS


class VoteWindowSettingsRequest(BaseModel):
    """Default voting window length in hours for each topic priority."""

    high_hours: int = Field(ge=MIN_VOTE_WINDOW_HOURS, le=MAX_VOTE_WINDOW_HOURS)
    medium_hours: int = Field(ge=MIN_VOTE_WINDOW_HOURS, le=MAX_VOTE_WINDOW_HOURS)
    low_hours: int = Field(ge=MIN_VOTE_WINDOW_HOURS, le=MAX_VOTE_WINDOW_HOURS)


class VoteWindowSettingsResponse(BaseModel):
    """The building's default voting window length in hours for each priority."""

    high_hours: int
    medium_hours: int
    low_hours: int
