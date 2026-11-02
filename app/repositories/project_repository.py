"""Persistence for building projects."""

from datetime import date, datetime, timezone
from typing import Protocol

from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from app.domain.projects import ProjectAttachmentRecord, ProjectRecord
from app.models.projects import ProjectAttachmentModel, ProjectModel


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

    def list_attachments_for_projects(self, project_ids: list[str]) -> list[ProjectAttachmentRecord]:
        """Return every attachment for the given projects."""

    def replace_attachments(self, project_id: str, attachments: list[ProjectAttachmentRecord]) -> None:
        """Replace every attachment for one project."""


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
        created = datetime.fromisoformat(project.created_at.replace("Z", "+00:00"))
        self._session.add(
            ProjectModel(
                id=project.id,
                period_id=project.period_id,
                title=project.title,
                description=project.description,
                photo_names=project.photo_names,
                due_date=date.fromisoformat(project.due_date) if project.due_date else None,
                created_at=created,
            ),
        )
        self._session.flush()
        stored = self._session.get(ProjectModel, project.id)
        if stored is None:
            return project
        return self._record(stored)

    def update_project(self, project: ProjectRecord) -> ProjectRecord:
        row = self._session.get(ProjectModel, project.id)
        if row is None:
            raise LookupError(project.id)
        row.period_id = project.period_id
        row.title = project.title
        row.description = project.description
        row.photo_names = project.photo_names
        row.due_date = date.fromisoformat(project.due_date) if project.due_date else None
        self._session.flush()
        return self._record(row)

    def delete_project(self, project_id: str) -> None:
        bind = self._session.get_bind()
        if bind is not None and inspect(bind).has_table("project_attachments"):
            self._session.execute(
                delete(ProjectAttachmentModel).where(ProjectAttachmentModel.project_id == project_id),
            )
        row = self._session.get(ProjectModel, project_id)
        if row is not None:
            self._session.delete(row)

    def list_attachments_for_projects(self, project_ids: list[str]) -> list[ProjectAttachmentRecord]:
        if not project_ids:
            return []
        bind = self._session.get_bind()
        if bind is None or not inspect(bind).has_table("project_attachments"):
            return []
        rows = self._session.scalars(
            select(ProjectAttachmentModel)
            .where(ProjectAttachmentModel.project_id.in_(project_ids))
            .order_by(ProjectAttachmentModel.name),
        ).all()
        return [self._attachment(row) for row in rows]

    def replace_attachments(self, project_id: str, attachments: list[ProjectAttachmentRecord]) -> None:
        bind = self._session.get_bind()
        if bind is None or not inspect(bind).has_table("project_attachments"):
            return
        self._session.execute(
            delete(ProjectAttachmentModel).where(ProjectAttachmentModel.project_id == project_id),
        )
        for attachment in attachments:
            self._session.add(
                ProjectAttachmentModel(
                    id=attachment.id,
                    project_id=attachment.project_id,
                    kind=attachment.kind,
                    name=attachment.name,
                    url=attachment.url,
                ),
            )

    def _record(self, row: ProjectModel) -> ProjectRecord:
        created = row.created_at
        if created is None:
            created_at = datetime.now(timezone.utc).isoformat()
        elif created.tzinfo is None:
            created_at = created.replace(tzinfo=timezone.utc).isoformat()
        else:
            created_at = created.isoformat()
        due = getattr(row, "due_date", None)
        return ProjectRecord(
            id=row.id,
            period_id=row.period_id,
            title=row.title,
            description=row.description,
            photo_names=row.photo_names,
            created_at=created_at,
            due_date=due.isoformat() if due else None,
        )

    def _attachment(self, row: ProjectAttachmentModel) -> ProjectAttachmentRecord:
        return ProjectAttachmentRecord(
            id=row.id,
            project_id=row.project_id,
            kind=row.kind,
            name=row.name,
            url=row.url,
        )
