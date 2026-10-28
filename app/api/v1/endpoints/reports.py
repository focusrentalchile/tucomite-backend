"""Report endpoints for building owners."""

from fastapi import APIRouter, Depends

from app.api.deps import Actor, get_current_actor, get_report_service
from app.schemas.reports import (
    ReportSummaryResponse,
    ResolvedCategoryCount,
    ResolvedTopicItem,
    ResolvedTopicsReportResponse,
    ResponseTimeItem,
    ResponseTimeReportResponse,
)
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])


@router.get("/reports/summary", response_model=ReportSummaryResponse)
def read_report_summary(
    service: ReportService = Depends(get_report_service),
    _: Actor = Depends(get_current_actor),
) -> ReportSummaryResponse:
    """Return owner-facing counts for topics, votes, and projects."""
    data = service.summary()
    return ReportSummaryResponse(
        topics_opened=int(data["topics_opened"]),
        topics_open=int(data["topics_open"]),
        topics_waiting=int(data["topics_waiting"]),
        topics_in_progress=int(data["topics_in_progress"]),
        topics_with_result=int(data["topics_with_result"]),
        votes_cast=int(data["votes_cast"]),
        projects_count=int(data["projects_count"]),
        open_period_name=str(data["open_period_name"]),
    )


@router.get("/reports/response-time", response_model=ResponseTimeReportResponse)
def read_response_time_report(
    service: ReportService = Depends(get_report_service),
    _: Actor = Depends(get_current_actor),
) -> ResponseTimeReportResponse:
    """How long the committee takes to close topics."""
    data = service.response_time()
    return ResponseTimeReportResponse(
        average_seconds=data["average_seconds"],
        fastest_seconds=data["fastest_seconds"],
        slowest_seconds=data["slowest_seconds"],
        average_label=str(data["average_label"]),
        fastest_label=str(data["fastest_label"]),
        slowest_label=str(data["slowest_label"]),
        items=[ResponseTimeItem(**item) for item in data["items"]],
    )


@router.get("/reports/resolved-topics", response_model=ResolvedTopicsReportResponse)
def read_resolved_topics_report(
    service: ReportService = Depends(get_report_service),
    _: Actor = Depends(get_current_actor),
) -> ResolvedTopicsReportResponse:
    """How many topics were resolved, with priority and category breakdown."""
    data = service.resolved_topics()
    return ResolvedTopicsReportResponse(
        total_resolved=int(data["total_resolved"]),
        open_period_name=str(data["open_period_name"]),
        by_priority=dict(data["by_priority"]),
        by_category=[ResolvedCategoryCount(**item) for item in data["by_category"]],
        items=[ResolvedTopicItem(**item) for item in data["items"]],
    )
