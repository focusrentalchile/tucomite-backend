"""Build owner-facing summary counts from topics, votes, and projects."""

from app.domain.topics import OPEN_STATUS_ID, WAITING_STATUS_ID
from app.repositories.period_repository import PeriodRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.topic_repository import TopicRepository

CLOSED_STATUS_ID = 4
DOING_STATUS_ID = 3


class ReportService:
    """Application rules for report summaries."""

    def __init__(
        self,
        topics: TopicRepository,
        projects: ProjectRepository,
        periods: PeriodRepository,
    ) -> None:
        self._topics = topics
        self._projects = projects
        self._periods = periods

    def summary(self) -> dict[str, int | str]:
        """Return the counts shown on the Informes page."""
        topics = self._topics.list_topics()
        votes = self._topics.list_votes_for_topics([topic.id for topic in topics])
        open_period = self._periods.get_open_period()
        return {
            "topics_opened": len(topics),
            "topics_open": sum(1 for topic in topics if topic.status_id == OPEN_STATUS_ID),
            "topics_waiting": sum(1 for topic in topics if topic.status_id == WAITING_STATUS_ID),
            "topics_in_progress": sum(1 for topic in topics if topic.status_id == DOING_STATUS_ID),
            "topics_with_result": sum(1 for topic in topics if topic.status_id == CLOSED_STATUS_ID),
            "votes_cast": len(votes),
            "projects_count": len(self._projects.list_projects()),
            "open_period_name": open_period.name if open_period is not None else "",
        }
