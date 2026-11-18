"""Schemas for per-building settings."""

from pydantic import BaseModel, Field

from app.domain.client_settings import (
    MAX_CONSENSUS_GRACE_DAYS,
    MAX_VOTE_WINDOW_HOURS,
    MIN_CONSENSUS_GRACE_DAYS,
    MIN_VOTE_WINDOW_HOURS,
)


class VoteWindowSettingsRequest(BaseModel):
    """Default voting window length in hours for each topic priority."""

    high_hours: int = Field(ge=MIN_VOTE_WINDOW_HOURS, le=MAX_VOTE_WINDOW_HOURS)
    medium_hours: int = Field(ge=MIN_VOTE_WINDOW_HOURS, le=MAX_VOTE_WINDOW_HOURS)
    low_hours: int = Field(ge=MIN_VOTE_WINDOW_HOURS, le=MAX_VOTE_WINDOW_HOURS)
    consensus_grace_days: int = Field(ge=MIN_CONSENSUS_GRACE_DAYS, le=MAX_CONSENSUS_GRACE_DAYS)


class VoteWindowSettingsResponse(BaseModel):
    """The building's default voting window length in hours for each priority."""

    high_hours: int
    medium_hours: int
    low_hours: int
    consensus_grace_days: int


class BuildingProfileResponse(BaseModel):
    """Public building identity shown in Configuración and the admin chrome."""

    name: str
    logo_url: str = ""
    identification_number: str = ""


class BuildingProfileRequest(BaseModel):
    """Editable building name, identification number, and optional logo."""

    name: str = Field(min_length=1, max_length=160)
    logo_url: str = Field(default="", max_length=6_000_000)
    identification_number: str = Field(min_length=3, max_length=20)
