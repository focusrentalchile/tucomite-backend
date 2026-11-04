"""Create, update, list, and delete building projects."""

from datetime import date, datetime, timezone
from uuid import uuid4

from app.domain.periods import NoOpenPeriod, PeriodNotFound
from app.domain.projects import ATTACHMENT_KINDS, ProjectAttachmentRecord, ProjectNotFound, ProjectRecord
from app.repositories.period_repository import PeriodRepository
from app.repositories.project_repository import ProjectRepository


class ProjectService:
    """Application rules for projects."""

    def __init__(self, repository: ProjectRepository, periods: PeriodRepository) -> None:
        self._repository = repository
        self._periods = periods

    def list_projects(self, period_id: str | None = None) -> list[ProjectRecord]:
        """Return projects, optionally for one period."""
        return self._repository.list_projects(period_id)

    def list_attachments_for_projects(self, project_ids: list[str]) -> list[ProjectAttachmentRecord]:
        """Return every attachment for the given projects."""
        return self._repository.list_attachments_for_projects(project_ids)

    def create_project(
        self,
        period_id: str,
        title: str,
        description: str,
        photo_names: str = "",
        *,
        due_date: str | None = None,
        attachments: list[dict[str, str]] | None = None,
    ) -> ProjectRecord:
        """Store a new project inside an existing period."""
        period = self._periods.get_period(period_id)
        if period is None:
            raise PeriodNotFound(period_id)
        if not period.client_id:
            raise NoOpenPeriod(period_id)
        open_period = self._periods.get_open_period(period.client_id)
        if open_period is None or open_period.id != period_id:
            raise NoOpenPeriod(period_id)
        project_id = str(uuid4())
        normalized = self._normalize_attachments(project_id, attachments)
        names = photo_names.strip() or ", ".join(item.name for item in normalized)
        record = self._repository.create_project(
            ProjectRecord(
                id=project_id,
                period_id=period_id,
                title=title.strip(),
                description=description.strip(),
                photo_names=names[:1000],
                created_at=datetime.now(timezone.utc).isoformat(),
                due_date=self._normalize_due_date(due_date),
            ),
        )
        self._repository.replace_attachments(project_id, normalized)
        return record

    def update_project(
        self,
        project_id: str,
        title: str,
        description: str,
        photo_names: str = "",
        *,
        due_date: str | None = None,
        attachments: list[dict[str, str]] | None = None,
    ) -> ProjectRecord:
        """Replace the editable fields of one project."""
        current = self._repository.get_project(project_id)
        if current is None:
            raise ProjectNotFound(project_id)
        normalized = self._normalize_attachments(project_id, attachments)
        names = photo_names.strip() or ", ".join(item.name for item in normalized)
        record = self._repository.update_project(
            ProjectRecord(
                id=project_id,
                period_id=current.period_id,
                title=title.strip(),
                description=description.strip(),
                photo_names=names[:1000],
                created_at=current.created_at,
                due_date=self._normalize_due_date(due_date),
            ),
        )
        self._repository.replace_attachments(project_id, normalized)
        return record

    def delete_project(self, project_id: str) -> None:
        """Remove one project."""
        if self._repository.get_project(project_id) is None:
            raise ProjectNotFound(project_id)
        self._repository.delete_project(project_id)

    def _normalize_due_date(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        return date.fromisoformat(cleaned[:10]).isoformat()

    def _normalize_attachments(
        self,
        project_id: str,
        attachments: list[dict[str, str]] | None,
    ) -> list[ProjectAttachmentRecord]:
        stored: list[ProjectAttachmentRecord] = []
        for item in attachments or []:
            kind = str(item.get("kind", "")).strip().lower()
            name = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
            if kind not in ATTACHMENT_KINDS or not name or not url:
                continue
            stored.append(
                ProjectAttachmentRecord(
                    id=str(uuid4()),
                    project_id=project_id,
                    kind=kind,
                    name=name[:255],
                    url=url,
                ),
            )
        return stored
