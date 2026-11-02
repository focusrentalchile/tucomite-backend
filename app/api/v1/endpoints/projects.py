"""Project endpoints. Only committee members may use them."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import Actor, get_project_service, require_committee_member
from app.domain.periods import NoOpenPeriod, PeriodNotFound
from app.domain.projects import ProjectAttachmentRecord, ProjectNotFound, ProjectRecord
from app.schemas.projects import (
    CreateProjectRequest,
    ProjectAttachmentResponse,
    ProjectListResponse,
    ProjectResponse,
    UpdateProjectRequest,
)
from app.services.project_service import ProjectService

router = APIRouter(tags=["projects"])


def _attachment_response(attachment: ProjectAttachmentRecord) -> ProjectAttachmentResponse:
    return ProjectAttachmentResponse(
        id=attachment.id,
        kind=attachment.kind,
        name=attachment.name,
        url=attachment.url,
    )


def _project_response(
    project: ProjectRecord,
    attachments: list[ProjectAttachmentRecord] | None = None,
) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        period_id=project.period_id,
        title=project.title,
        description=project.description,
        photo_names=project.photo_names,
        created_at=project.created_at,
        due_date=project.due_date,
        attachments=[_attachment_response(item) for item in (attachments or [])],
    )


@router.get("/projects", response_model=ProjectListResponse)
def read_projects(
    period_id: str | None = Query(default=None),
    service: ProjectService = Depends(get_project_service),
    _: Actor = Depends(require_committee_member),
) -> ProjectListResponse:
    """Return projects. Only committee members may look."""
    projects = service.list_projects(period_id)
    attachments = service.list_attachments_for_projects([item.id for item in projects])
    by_project: dict[str, list[ProjectAttachmentRecord]] = {item.id: [] for item in projects}
    for attachment in attachments:
        by_project.setdefault(attachment.project_id, []).append(attachment)
    return ProjectListResponse(
        items=[_project_response(project, by_project.get(project.id, [])) for project in projects],
    )


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    body: CreateProjectRequest,
    service: ProjectService = Depends(get_project_service),
    _: Actor = Depends(require_committee_member),
) -> ProjectResponse:
    """Create a project in the open period. Only committee members may create."""
    try:
        project = service.create_project(
            body.period_id,
            body.title,
            body.description,
            body.photo_names,
            due_date=body.due_date,
            attachments=[item.model_dump() for item in body.attachments],
        )
    except PeriodNotFound as error:
        raise HTTPException(status_code=404, detail="Period not found.") from error
    except NoOpenPeriod as error:
        raise HTTPException(status_code=409, detail="Period is not open.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    stored = service.list_attachments_for_projects([project.id])
    return _project_response(project, stored)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    service: ProjectService = Depends(get_project_service),
    _: Actor = Depends(require_committee_member),
) -> ProjectResponse:
    """Update one project. Only committee members may edit."""
    try:
        project = service.update_project(
            project_id,
            body.title,
            body.description,
            body.photo_names,
            due_date=body.due_date,
            attachments=[item.model_dump() for item in body.attachments],
        )
    except ProjectNotFound as error:
        raise HTTPException(status_code=404, detail="Project not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    stored = service.list_attachments_for_projects([project.id])
    return _project_response(project, stored)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
    _: Actor = Depends(require_committee_member),
) -> None:
    """Delete one project. Only committee members may delete."""
    try:
        service.delete_project(project_id)
    except ProjectNotFound as error:
        raise HTTPException(status_code=404, detail="Project not found.") from error
