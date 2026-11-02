"""Request and response shapes for agreements."""

from pydantic import BaseModel


class AgreementResponse(BaseModel):
    """One published agreement."""

    id: str
    topic_id: str
    period_id: str | None = None
    client_id: str | None = None
    title: str
    decision: str
    description: str
    category_key: str
    summary: str
    vote_yes: int
    vote_no: int
    vote_abstain: int
    vote_result: str
    closed_at: str | None = None
    created_at: str
    pdf_name: str


class AgreementListResponse(BaseModel):
    """Agreement collection."""

    items: list[AgreementResponse]
