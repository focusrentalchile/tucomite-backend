"""Unit tests for owner-facing report counts."""

from app.domain.periods import PERIOD_STATUS_OPEN, PeriodRecord
from app.domain.projects import ProjectRecord
from app.domain.topics import OPEN_STATUS_ID, WAITING_STATUS_ID, TopicRecord, TopicVoteRecord
from app.services.report_service import ReportService
from tests.support.memory_period_repository import InMemoryPeriodRepository
from tests.support.memory_project_repository import InMemoryProjectRepository


class _TopicRepo:
    def __init__(self) -> None:
        self.topics = [
            TopicRecord("t1", "A", "d", "other", "", "?", OPEN_STATUS_ID, 1),
            TopicRecord("t2", "B", "d", "other", "", "?", WAITING_STATUS_ID, 2),
            TopicRecord("t3", "C", "d", "other", "", "?", 4, 3),
        ]
        self.votes = [
            TopicVoteRecord("v1", "t2", "u1", "Ana", "yes"),
            TopicVoteRecord("v2", "t2", "u2", "Luis", "no"),
        ]

    def list_topics(self) -> list[TopicRecord]:
        return self.topics

    def list_votes_for_topics(self, topic_ids: list[str]) -> list[TopicVoteRecord]:
        return [vote for vote in self.votes if vote.topic_id in topic_ids]


def test_report_summary_counts_topics_votes_and_projects() -> None:
    periods = InMemoryPeriodRepository()
    periods.create_period(PeriodRecord(id="per1", name="2026", status=PERIOD_STATUS_OPEN))
    projects = InMemoryProjectRepository()
    projects.create_project(
        ProjectRecord(id="p1", period_id="per1", title="Fachada", description="Pintar", photo_names=""),
    )
    service = ReportService(_TopicRepo(), projects, periods)

    summary = service.summary()

    assert summary["topics_opened"] == 3
    assert summary["topics_open"] == 1
    assert summary["topics_waiting"] == 1
    assert summary["topics_with_result"] == 1
    assert summary["votes_cast"] == 2
    assert summary["projects_count"] == 1
    assert summary["open_period_name"] == "2026"
