"""Create, update, list, and delete building projects."""

from uuid import uuid4

from app.domain.periods import NoOpenPeriod, PeriodNotFound
from app.domain.projects import ProjectNotFound, ProjectRecord
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

    def create_project(
        self,
        period_id: str,
        title: str,
        description: str,
        photo_names: str,
    ) -> ProjectRecord:
        """Store a new project inside an existing period."""
        period = self._periods.get_period(period_id)
        if period is None:
            raise PeriodNotFound(period_id)
        open_period = self._periods.get_open_period()
        if open_period is None or open_period.id != period_id:
            raise NoOpenPeriod(period_id)
        return self._repository.create_project(
            ProjectRecord(
                id=str(uuid4()),
                period_id=period_id,
                title=title.strip(),
                description=description.strip(),
                photo_names=photo_names.strip(),
            ),
        )

    def update_project(
        self,
        project_id: str,
        title: str,
        description: str,
        photo_names: str,
    ) -> ProjectRecord:
        """Replace the editable fields of one project."""
        current = self._repository.get_project(project_id)
        if current is None:
            raise ProjectNotFound(project_id)
        return self._repository.update_project(
            ProjectRecord(
                id=project_id,
                period_id=current.period_id,
                title=title.strip(),
                description=description.strip(),
                photo_names=photo_names.strip(),
            ),
        )

    def delete_project(self, project_id: str) -> None:
        """Remove one project."""
        if self._repository.get_project(project_id) is None:
            raise ProjectNotFound(project_id)
        self._repository.delete_project(project_id)
