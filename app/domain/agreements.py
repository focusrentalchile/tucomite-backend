"""Stored agreements published from closed topics."""

from dataclasses import dataclass


VOTE_RESULT_APPROVED = "approved"
VOTE_RESULT_REJECTED = "rejected"
VOTE_RESULT_TIED = "tied"
VOTE_RESULT_NO_VOTES = "no_votes"


@dataclass(frozen=True)
class AgreementRecord:
    """One published agreement with an attached PDF report."""

    id: str
    topic_id: str
    period_id: str | None
    client_id: str | None
    title: str
    decision: str
    description: str
    category_key: str
    summary: str
    vote_yes: int
    vote_no: int
    vote_abstain: int
    vote_result: str
    closed_at: str | None
    created_at: str
    pdf_name: str


@dataclass(frozen=True)
class AgreementDetailRecord(AgreementRecord):
    """Agreement plus PDF bytes for download."""

    pdf_bytes: bytes


class AgreementNotFound(Exception):
    """Raised when an agreement id does not exist."""
