"""Project endpoints. Only committee members may use them."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import Actor, get_project_service, require_committee_member
from app.domain.periods import NoOpenPeriod, PeriodNotFound
from app.domain.projects import ProjectNotFound, ProjectRecord
from app.schemas.projects import (
    CreateProjectRequest,
    ProjectListResponse,
    ProjectResponse,
    UpdateProjectRequest,
)
from app.services.project_service import ProjectService

router = APIRouter(tags=["projects"])


def _project_response(project: ProjectRecord) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        period_id=project.period_id,
        title=project.title,
        description=project.description,
        photo_names=project.photo_names,
    )


@router.get("/projects", response_model=ProjectListResponse)
def read_projects(
    period_id: str | None = Query(default=None),
    service: ProjectService = Depends(get_project_service),
    _: Actor = Depends(require_committee_member),
) -> ProjectListResponse:
    """Return projects. Only committee members may look."""
    return ProjectListResponse(
        items=[_project_response(project) for project in service.list_projects(period_id)],
    )


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    body: CreateProjectRequest,
    service: ProjectService = Depends(get_project_service),
    _: Actor = Depends(require_committee_member),
) -> ProjectResponse:
    """Create a project in the open period. Only committee members may create."""
    try:
        project = service.create_project(body.period_id, body.title, body.description, body.photo_names)
    except PeriodNotFound as error:
        raise HTTPException(status_code=404, detail="Period not found.") from error
    except NoOpenPeriod as error:
        raise HTTPException(status_code=409, detail="Period is not open.") from error
    return _project_response(project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    service: ProjectService = Depends(get_project_service),
    _: Actor = Depends(require_committee_member),
) -> ProjectResponse:
    """Update one project. Only committee members may edit."""
    try:
        project = service.update_project(project_id, body.title, body.description, body.photo_names)
    except ProjectNotFound as error:
        raise HTTPException(status_code=404, detail="Project not found.") from error
    return _project_response(project)


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
