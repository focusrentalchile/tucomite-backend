"""In-memory project repository for unit tests."""

from app.domain.projects import ProjectRecord


class InMemoryProjectRepository:
    """Stores projects in a dict keyed by id."""

    def __init__(self) -> None:
        self._projects: dict[str, ProjectRecord] = {}

    def list_projects(self, period_id: str | None = None) -> list[ProjectRecord]:
        items = list(self._projects.values())
        if period_id is not None:
            items = [project for project in items if project.period_id == period_id]
        return sorted(items, key=lambda project: project.title)

    def get_project(self, project_id: str) -> ProjectRecord | None:
        return self._projects.get(project_id)

    def create_project(self, project: ProjectRecord) -> ProjectRecord:
        self._projects[project.id] = project
        return project

    def update_project(self, project: ProjectRecord) -> ProjectRecord:
        self._projects[project.id] = project
        return project

    def delete_project(self, project_id: str) -> None:
        self._projects.pop(project_id, None)
