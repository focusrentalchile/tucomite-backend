"""Response shapes for owner-facing reports."""

from pydantic import BaseModel


class ReportSummaryResponse(BaseModel):
    """Counts that building owners need to see at a glance."""

    topics_opened: int
    topics_open: int
    topics_waiting: int
    topics_in_progress: int
    topics_with_result: int
    votes_cast: int
    projects_count: int
    open_period_name: str
