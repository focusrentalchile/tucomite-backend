"""Persistence for building projects."""

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.projects import ProjectRecord
from app.models.projects import ProjectModel


class ProjectRepository(Protocol):
    """Persistence port used by the project service."""

    def list_projects(self, period_id: str | None = None) -> list[ProjectRecord]:
        """Return projects, optionally filtered by period."""

    def get_project(self, project_id: str) -> ProjectRecord | None:
        """Return one project when present."""

    def create_project(self, project: ProjectRecord) -> ProjectRecord:
        """Insert one project."""

    def update_project(self, project: ProjectRecord) -> ProjectRecord:
        """Replace one project."""

    def delete_project(self, project_id: str) -> None:
        """Delete one project."""


class SqlProjectRepository:
    """SQLAlchemy adapter for the projects table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_projects(self, period_id: str | None = None) -> list[ProjectRecord]:
        query = select(ProjectModel).order_by(ProjectModel.title)
        if period_id is not None:
            query = query.where(ProjectModel.period_id == period_id)
        rows = self._session.execute(query).scalars().all()
        return [self._record(row) for row in rows]

    def get_project(self, project_id: str) -> ProjectRecord | None:
        row = self._session.get(ProjectModel, project_id)
        if row is None:
            return None
        return self._record(row)

    def create_project(self, project: ProjectRecord) -> ProjectRecord:
        self._session.add(
            ProjectModel(
                id=project.id,
                period_id=project.period_id,
                title=project.title,
                description=project.description,
                photo_names=project.photo_names,
            ),
        )
        self._session.flush()
        return project

    def update_project(self, project: ProjectRecord) -> ProjectRecord:
        row = self._session.get(ProjectModel, project.id)
        if row is None:
            raise LookupError(project.id)
        row.period_id = project.period_id
        row.title = project.title
        row.description = project.description
        row.photo_names = project.photo_names
        self._session.flush()
        return project

    def delete_project(self, project_id: str) -> None:
        row = self._session.get(ProjectModel, project_id)
        if row is not None:
            self._session.delete(row)

    def _record(self, row: ProjectModel) -> ProjectRecord:
        return ProjectRecord(
            id=row.id,
            period_id=row.period_id,
            title=row.title,
            description=row.description,
            photo_names=row.photo_names,
        )
