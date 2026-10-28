"""Platform management task and Gestión workspace endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_current_actor, require_permission
from app.core.database import get_db
from app.domain.management import TaskNotFound
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.client_repository import SqlClientRepository
from app.repositories.management_repository import SqlManagementRepository
from app.repositories.notification_repository import SqlNotificationRepository
from app.schemas.management import (
    CreateManagementMessageRequest,
    CreateManagementTaskRequest,
    CreateManagementWorkspaceImportRequest,
    ManagementMessageResponse,
    ManagementTaskListResponse,
    ManagementTaskResponse,
    ManagementWorkspaceClientListResponse,
    ManagementWorkspaceClientResponse,
    ManagementWorkspaceImportListResponse,
    ManagementWorkspaceImportResponse,
    UpdateManagementTaskStatusRequest,
)
from app.services.management_service import ManagementService

router = APIRouter(prefix="/management", tags=["management"])


def get_management_service(db: Session = Depends(get_db)) -> ManagementService:
    """Build a management service for the request."""
    return ManagementService(
        SqlManagementRepository(db),
        clients=SqlClientRepository(db),
        access=SqlAccessRepository(db),
        notifications=SqlNotificationRepository(db),
    )


def _message_response(message) -> ManagementMessageResponse:
    return ManagementMessageResponse(
        id=message.id,
        author_user_id=message.author_user_id,
        author_name=message.author_name,
        body=message.body,
        created_at=message.created_at,
        from_staff=message.from_staff,
    )


def _task_response(ticket) -> ManagementTaskResponse:
    return ManagementTaskResponse(
        id=ticket.id,
        client_id=ticket.client_id,
        client_name=ticket.client_name,
        created_by_user_id=ticket.created_by_user_id,
        created_by_name=ticket.created_by_name,
        subject=ticket.subject,
        status=ticket.status,
        priority_id=ticket.priority_id,
        due_date=ticket.due_date,
        assignee_user_id=ticket.assignee_user_id,
        topic_id=ticket.topic_id,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        messages=[_message_response(item) for item in ticket.messages],
    )


def _import_response(record) -> ManagementWorkspaceImportResponse:
    return ManagementWorkspaceImportResponse(
        id=record.id,
        administrator_user_id=record.administrator_user_id,
        administrator_name=record.administrator_name,
        administrator_email=record.administrator_email,
        client_id=record.client_id,
        client_name=record.client_name,
        status=record.status,
        created_at=record.created_at,
        resolved_at=record.resolved_at,
    )


def _actor_name(db: Session, user_id: str) -> str:
    user = SqlAccessRepository(db).get_user(user_id)
    return user.full_name if user is not None else ""


def _client_name(db: Session, client_id: str | None) -> str:
    if not client_id:
        return ""
    client = SqlClientRepository(db).get_client(client_id)
    return client.name if client is not None else ""


def _owned_client_id(db: Session, actor: Actor) -> str | None:
    """Return the building id when the actor is that building's owner account."""
    clients = SqlClientRepository(db)
    for client in clients.list_clients():
        if client.admin_user_id == actor.user_id:
            return client.id
    if actor.client_id:
        client = clients.get_client(actor.client_id)
        if client is not None and client.admin_user_id == actor.user_id:
            return client.id
    return None


def _workspace_ids(service: ManagementService, actor: Actor) -> list[str] | None:
    """None means every building (super admin); otherwise the workspace set."""
    if actor.is_super_admin:
        return None
    return service.workspace_client_ids(user_id=actor.user_id, home_client_id=actor.client_id)


def _ensure_task_access(service: ManagementService, actor: Actor, task_client_id: str | None) -> None:
    if actor.is_super_admin:
        return
    allowed = _workspace_ids(service, actor) or []
    if not task_client_id or task_client_id not in allowed:
        raise HTTPException(status_code=404, detail="Ticket not found.")


@router.get("/workspace/clients", response_model=ManagementWorkspaceClientListResponse)
def list_workspace_clients(
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "view")),
) -> ManagementWorkspaceClientListResponse:
    """List buildings available on this administrator's Gestión board."""
    if actor.is_super_admin:
        return ManagementWorkspaceClientListResponse(items=[])
    items = service.list_workspace_clients(user_id=actor.user_id, home_client_id=actor.client_id)
    return ManagementWorkspaceClientListResponse(
        items=[
            ManagementWorkspaceClientResponse(
                client_id=item.client_id,
                client_name=item.client_name,
                home=item.home,
            )
            for item in items
        ],
    )


@router.get("/workspace/imports", response_model=ManagementWorkspaceImportListResponse)
def list_workspace_imports(
    scope: str = Query(default="outgoing"),
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> ManagementWorkspaceImportListResponse:
    """List outgoing requests (administrator) or incoming pending approvals (owner)."""
    cleaned = scope.strip().lower()
    if cleaned == "incoming":
        owned = _owned_client_id(db, actor)
        if not owned and "management.approve_import" not in actor.permissions:
            raise HTTPException(status_code=403, detail="Forbidden.")
        if not owned:
            return ManagementWorkspaceImportListResponse(items=[])
        items = service.list_incoming_imports(owned)
        return ManagementWorkspaceImportListResponse(items=[_import_response(item) for item in items])
    if "management.create" not in actor.permissions and "management.view" not in actor.permissions:
        raise HTTPException(status_code=403, detail="Forbidden.")
    items = service.list_outgoing_imports(actor.user_id)
    return ManagementWorkspaceImportListResponse(items=[_import_response(item) for item in items])


@router.post("/workspace/imports", response_model=ManagementWorkspaceImportResponse, status_code=201)
def create_workspace_import(
    body: CreateManagementWorkspaceImportRequest,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "create")),
) -> ManagementWorkspaceImportResponse:
    """Request permission to import another building into Gestión."""
    if actor.is_super_admin:
        raise HTTPException(status_code=403, detail="Staff does not import buildings into Gestión.")
    try:
        record = service.request_import(
            administrator_user_id=actor.user_id,
            home_client_id=actor.client_id,
            owner_email=body.owner_email,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _import_response(record)


@router.post("/workspace/imports/{import_id}/approve", response_model=ManagementWorkspaceImportResponse)
def approve_workspace_import(
    import_id: str,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(get_current_actor),
) -> ManagementWorkspaceImportResponse:
    """Building owner approves an administrator's Gestión import request."""
    try:
        record = service.resolve_import(import_id, approve=True, owner_user_id=actor.user_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Import request not found.") from None
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden.") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _import_response(record)


@router.post("/workspace/imports/{import_id}/reject", response_model=ManagementWorkspaceImportResponse)
def reject_workspace_import(
    import_id: str,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(get_current_actor),
) -> ManagementWorkspaceImportResponse:
    """Building owner rejects an administrator's Gestión import request."""
    try:
        record = service.resolve_import(import_id, approve=False, owner_user_id=actor.user_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Import request not found.") from None
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden.") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _import_response(record)


@router.get("/tasks", response_model=ManagementTaskListResponse)
def list_tasks(
    client_id: str | None = Query(default=None),
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "view")),
) -> ManagementTaskListResponse:
    """List tasks for the actor's Gestión workspace, optionally filtered by client."""
    if actor.is_super_admin:
        tasks = service.list_tasks(client_id=client_id)
        return ManagementTaskListResponse(items=[_task_response(item) for item in tasks])
    allowed = _workspace_ids(service, actor) or []
    if not allowed:
        return ManagementTaskListResponse(items=[])
    if client_id:
        if client_id not in allowed:
            return ManagementTaskListResponse(items=[])
        tasks = service.list_tasks(client_id=client_id)
    else:
        tasks = service.list_tasks(client_ids=allowed)
    return ManagementTaskListResponse(items=[_task_response(item) for item in tasks])


@router.get("/tasks/{task_id}", response_model=ManagementTaskResponse)
def read_task(
    task_id: str,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "view")),
) -> ManagementTaskResponse:
    """Return one ticket thread."""
    try:
        ticket = service.get_task(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    _ensure_task_access(service, actor, ticket.client_id)
    return _task_response(ticket)


@router.post("/tasks", response_model=ManagementTaskResponse, status_code=201)
def create_task(
    body: CreateManagementTaskRequest,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "create")),
    db: Session = Depends(get_db),
) -> ManagementTaskResponse:
    """Open a management task for a building in the actor's Gestión workspace."""
    if actor.is_super_admin:
        raise HTTPException(status_code=403, detail="Staff replies on existing tasks.")
    allowed = _workspace_ids(service, actor) or []
    target_client_id = body.client_id or actor.client_id
    if not target_client_id or target_client_id not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden.")
    try:
        ticket = service.create_task(
            subject=body.subject,
            body=body.body,
            created_by_user_id=actor.user_id,
            created_by_name=_actor_name(db, actor.user_id),
            client_id=target_client_id,
            client_name=_client_name(db, target_client_id),
            from_staff=False,
            priority_id=body.priority_id,
            due_date=body.due_date,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _task_response(ticket)


@router.post("/tasks/{task_id}/messages", response_model=ManagementTaskResponse, status_code=201)
def create_message(
    task_id: str,
    body: CreateManagementMessageRequest,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "reply")),
    db: Session = Depends(get_db),
) -> ManagementTaskResponse:
    """Add a reply to a ticket."""
    try:
        existing = service.get_task(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    _ensure_task_access(service, actor, existing.client_id)
    try:
        ticket = service.add_message(
            task_id,
            body=body.body,
            author_user_id=actor.user_id,
            author_name=_actor_name(db, actor.user_id),
            from_staff=actor.is_super_admin,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _task_response(ticket)


@router.patch("/tasks/{task_id}/status", response_model=ManagementTaskResponse)
def update_status(
    task_id: str,
    body: UpdateManagementTaskStatusRequest,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "reply")),
) -> ManagementTaskResponse:
    """Move a ticket across Pendientes / En curso / Completadas."""
    try:
        existing = service.get_task(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    _ensure_task_access(service, actor, existing.client_id)
    try:
        ticket = service.set_status(task_id, body.status)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _task_response(ticket)
