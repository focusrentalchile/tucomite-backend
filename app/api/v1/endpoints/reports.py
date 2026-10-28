"""Report endpoints for building owners."""

from fastapi import APIRouter, Depends

from app.api.deps import Actor, get_current_actor, get_report_service
from app.schemas.reports import ReportSummaryResponse
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
