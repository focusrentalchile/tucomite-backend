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


class ResponseTimeItem(BaseModel):
    """One closed topic and how long it took to resolve."""

    topic_id: str
    title: str
    opened_at: str
    closed_at: str
    duration_seconds: int | None
    duration_label: str


class ResponseTimeReportResponse(BaseModel):
    """Committee response-time report."""

    average_seconds: int | None
    fastest_seconds: int | None
    slowest_seconds: int | None
    average_label: str
    fastest_label: str
    slowest_label: str
    items: list[ResponseTimeItem]


class ResolvedTopicItem(BaseModel):
    """One resolved topic row."""

    topic_id: str
    title: str
    priority_id: int
    category_key: str
    closed_at: str


class ResolvedCategoryCount(BaseModel):
    """Resolved topics counted by category."""

    category_key: str
    count: int


class ResolvedTopicsReportResponse(BaseModel):
    """Resolved-topics report with breakdowns."""

    total_resolved: int
    open_period_name: str
    by_priority: dict[str, int]
    by_category: list[ResolvedCategoryCount]
    items: list[ResolvedTopicItem]
