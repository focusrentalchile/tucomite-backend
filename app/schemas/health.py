"""Schemas for the health resource."""

from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    """Public health payload returned by GET /health."""

    status: str = Field(description="Process status in English.")
    service: str = Field(description="Stable service identifier.")
