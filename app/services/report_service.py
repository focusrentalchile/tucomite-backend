"""Build owner-facing report payloads from topics and projects."""

from datetime import datetime

from app.domain.topics import CLOSED_STATUS_ID, OPEN_STATUS_ID, WAITING_STATUS_ID
from app.repositories.period_repository import PeriodRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.topic_repository import TopicRepository

DOING_STATUS_ID = 3


class ReportService:
    """Application rules for report summaries and detail reports."""

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

    def response_time(self) -> dict:
        """Average / fastest / slowest resolution times for closed topics."""
        rows: list[dict] = []
        for topic in self._topics.list_topics():
            if topic.status_id != CLOSED_STATUS_ID:
                continue
            seconds = self._duration_seconds(topic.created_at, topic.closed_at)
            rows.append(
                {
                    "topic_id": topic.id,
                    "title": topic.title,
                    "opened_at": topic.created_at or "",
                    "closed_at": topic.closed_at or "",
                    "duration_seconds": seconds,
                    "duration_label": self._format_duration(seconds),
                }
            )
        measured = [row["duration_seconds"] for row in rows if row["duration_seconds"] is not None]
        average = int(sum(measured) / len(measured)) if measured else None
        fastest = min(measured) if measured else None
        slowest = max(measured) if measured else None
        return {
            "average_seconds": average,
            "fastest_seconds": fastest,
            "slowest_seconds": slowest,
            "average_label": self._format_duration(average),
            "fastest_label": self._format_duration(fastest),
            "slowest_label": self._format_duration(slowest),
            "items": rows,
        }

    def resolved_topics(self) -> dict:
        """Breakdown of closed topics by priority and category."""
        closed = [topic for topic in self._topics.list_topics() if topic.status_id == CLOSED_STATUS_ID]
        by_priority: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        by_category: dict[str, int] = {}
        items: list[dict] = []
        for topic in closed:
            key = {1: "high", 2: "medium", 3: "low"}.get(topic.priority_id, "medium")
            by_priority[key] = by_priority.get(key, 0) + 1
            by_category[topic.category_key] = by_category.get(topic.category_key, 0) + 1
            items.append(
                {
                    "topic_id": topic.id,
                    "title": topic.title,
                    "priority_id": topic.priority_id,
                    "category_key": topic.category_key,
                    "closed_at": topic.closed_at or "",
                }
            )
        open_period = self._periods.get_open_period()
        return {
            "total_resolved": len(closed),
            "open_period_name": open_period.name if open_period is not None else "",
            "by_priority": by_priority,
            "by_category": [
                {"category_key": key, "count": count}
                for key, count in sorted(by_category.items(), key=lambda item: (-item[1], item[0]))
            ],
            "items": items,
        }

    def _duration_seconds(self, started: str | None, ended: str | None) -> int | None:
        if not started or not ended:
            return None
        try:
            start = datetime.fromisoformat(started.replace("Z", ""))
            end = datetime.fromisoformat(ended.replace("Z", ""))
        except ValueError:
            return None
        return max(0, int((end - start).total_seconds()))

    def _format_duration(self, seconds: int | None) -> str:
        if seconds is None:
            return "—"
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        if days:
            return f"{days}d {hours}h"
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
