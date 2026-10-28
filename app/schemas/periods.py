"""Request and response shapes for periods."""

from pydantic import BaseModel, Field


class PeriodResponse(BaseModel):
    """One management period."""

    id: str
    name: str
    status: str


class PeriodListResponse(BaseModel):
    """Period collection."""

    items: list[PeriodResponse]


class OpenPeriodRequest(BaseModel):
    """Payload to open (aperturar) a period."""

    name: str = Field(min_length=1, max_length=120)
