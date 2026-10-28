"""Platform support ticket and Gestión workspace endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_current_actor, require_permission
from app.core.database import get_db
from app.domain.support import TicketNotFound
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.client_repository import SqlClientRepository
from app.repositories.support_repository import SqlSupportRepository
from app.schemas.support import (
    CreateSupportMessageRequest,
    CreateSupportTicketRequest,
    CreateSupportWorkspaceImportRequest,
    SupportMessageResponse,
    SupportTicketListResponse,
    SupportTicketResponse,
    SupportWorkspaceClientListResponse,
    SupportWorkspaceClientResponse,
    SupportWorkspaceImportListResponse,
    SupportWorkspaceImportResponse,
    UpdateSupportTicketStatusRequest,
)
from app.services.support_service import SupportService

router = APIRouter(prefix="/support", tags=["support"])


def get_support_service(db: Session = Depends(get_db)) -> SupportService:
    """Build a support service for the request."""
    return SupportService(
        SqlSupportRepository(db),
        clients=SqlClientRepository(db),
        access=SqlAccessRepository(db),
    )


def _message_response(message) -> SupportMessageResponse:
    return SupportMessageResponse(
        id=message.id,
        author_user_id=message.author_user_id,
        author_name=message.author_name,
        body=message.body,
        created_at=message.created_at,
        from_staff=message.from_staff,
    )


def _ticket_response(ticket) -> SupportTicketResponse:
    return SupportTicketResponse(
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


def _import_response(record) -> SupportWorkspaceImportResponse:
    return SupportWorkspaceImportResponse(
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


def _workspace_ids(service: SupportService, actor: Actor) -> list[str] | None:
    """None means every building (super admin); otherwise the workspace set."""
    if actor.is_super_admin:
        return None
    return service.workspace_client_ids(user_id=actor.user_id, home_client_id=actor.client_id)


def _ensure_ticket_access(service: SupportService, actor: Actor, ticket_client_id: str | None) -> None:
    if actor.is_super_admin:
        return
    allowed = _workspace_ids(service, actor) or []
    if not ticket_client_id or ticket_client_id not in allowed:
        raise HTTPException(status_code=404, detail="Ticket not found.")


@router.get("/workspace/clients", response_model=SupportWorkspaceClientListResponse)
def list_workspace_clients(
    service: SupportService = Depends(get_support_service),
    actor: Actor = Depends(require_permission("support", "view")),
) -> SupportWorkspaceClientListResponse:
    """List buildings available on this administrator's Gestión board."""
    if actor.is_super_admin:
        return SupportWorkspaceClientListResponse(items=[])
    items = service.list_workspace_clients(user_id=actor.user_id, home_client_id=actor.client_id)
    return SupportWorkspaceClientListResponse(
        items=[
            SupportWorkspaceClientResponse(
                client_id=item.client_id,
                client_name=item.client_name,
                home=item.home,
            )
            for item in items
        ],
    )


@router.get("/workspace/imports", response_model=SupportWorkspaceImportListResponse)
def list_workspace_imports(
    scope: str = Query(default="outgoing"),
    service: SupportService = Depends(get_support_service),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> SupportWorkspaceImportListResponse:
    """List outgoing requests (administrator) or incoming pending approvals (owner)."""
    cleaned = scope.strip().lower()
    if cleaned == "incoming":
        owned = _owned_client_id(db, actor)
        if not owned and "support.approve_import" not in actor.permissions:
            raise HTTPException(status_code=403, detail="Forbidden.")
        if not owned:
            return SupportWorkspaceImportListResponse(items=[])
        items = service.list_incoming_imports(owned)
        return SupportWorkspaceImportListResponse(items=[_import_response(item) for item in items])
    if "support.create" not in actor.permissions and "support.view" not in actor.permissions:
        raise HTTPException(status_code=403, detail="Forbidden.")
    items = service.list_outgoing_imports(actor.user_id)
    return SupportWorkspaceImportListResponse(items=[_import_response(item) for item in items])


@router.post("/workspace/imports", response_model=SupportWorkspaceImportResponse, status_code=201)
def create_workspace_import(
    body: CreateSupportWorkspaceImportRequest,
    service: SupportService = Depends(get_support_service),
    actor: Actor = Depends(require_permission("support", "create")),
) -> SupportWorkspaceImportResponse:
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


@router.post("/workspace/imports/{import_id}/approve", response_model=SupportWorkspaceImportResponse)
def approve_workspace_import(
    import_id: str,
    service: SupportService = Depends(get_support_service),
    actor: Actor = Depends(get_current_actor),
) -> SupportWorkspaceImportResponse:
    """Building owner approves an administrator's Gestión import request."""
    try:
        record = service.resolve_import(import_id, approve=True, owner_user_id=actor.user_id)
    except TicketNotFound:
        raise HTTPException(status_code=404, detail="Import request not found.") from None
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden.") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _import_response(record)


@router.post("/workspace/imports/{import_id}/reject", response_model=SupportWorkspaceImportResponse)
def reject_workspace_import(
    import_id: str,
    service: SupportService = Depends(get_support_service),
    actor: Actor = Depends(get_current_actor),
) -> SupportWorkspaceImportResponse:
    """Building owner rejects an administrator's Gestión import request."""
    try:
        record = service.resolve_import(import_id, approve=False, owner_user_id=actor.user_id)
    except TicketNotFound:
        raise HTTPException(status_code=404, detail="Import request not found.") from None
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden.") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _import_response(record)


@router.get("/tickets", response_model=SupportTicketListResponse)
def list_tickets(
    client_id: str | None = Query(default=None),
    service: SupportService = Depends(get_support_service),
    actor: Actor = Depends(require_permission("support", "view")),
) -> SupportTicketListResponse:
    """List tickets for the actor's Gestión workspace, optionally filtered by client."""
    if actor.is_super_admin:
        tickets = service.list_tickets(client_id=client_id)
        return SupportTicketListResponse(items=[_ticket_response(item) for item in tickets])
    allowed = _workspace_ids(service, actor) or []
    if not allowed:
        return SupportTicketListResponse(items=[])
    if client_id:
        if client_id not in allowed:
            return SupportTicketListResponse(items=[])
        tickets = service.list_tickets(client_id=client_id)
    else:
        tickets = service.list_tickets(client_ids=allowed)
    return SupportTicketListResponse(items=[_ticket_response(item) for item in tickets])


@router.get("/tickets/{ticket_id}", response_model=SupportTicketResponse)
def read_ticket(
    ticket_id: str,
    service: SupportService = Depends(get_support_service),
    actor: Actor = Depends(require_permission("support", "view")),
) -> SupportTicketResponse:
    """Return one ticket thread."""
    try:
        ticket = service.get_ticket(ticket_id)
    except TicketNotFound:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    _ensure_ticket_access(service, actor, ticket.client_id)
    return _ticket_response(ticket)


@router.post("/tickets", response_model=SupportTicketResponse, status_code=201)
def create_ticket(
    body: CreateSupportTicketRequest,
    service: SupportService = Depends(get_support_service),
    actor: Actor = Depends(require_permission("support", "create")),
    db: Session = Depends(get_db),
) -> SupportTicketResponse:
    """Open a support ticket for a building in the actor's Gestión workspace."""
    if actor.is_super_admin:
        raise HTTPException(status_code=403, detail="Staff replies on existing tickets.")
    allowed = _workspace_ids(service, actor) or []
    target_client_id = body.client_id or actor.client_id
    if not target_client_id or target_client_id not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden.")
    try:
        ticket = service.create_ticket(
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
    return _ticket_response(ticket)


@router.post("/tickets/{ticket_id}/messages", response_model=SupportTicketResponse, status_code=201)
def create_message(
    ticket_id: str,
    body: CreateSupportMessageRequest,
    service: SupportService = Depends(get_support_service),
    actor: Actor = Depends(require_permission("support", "reply")),
    db: Session = Depends(get_db),
) -> SupportTicketResponse:
    """Add a reply to a ticket."""
    try:
        existing = service.get_ticket(ticket_id)
    except TicketNotFound:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    _ensure_ticket_access(service, actor, existing.client_id)
    try:
        ticket = service.add_message(
            ticket_id,
            body=body.body,
            author_user_id=actor.user_id,
            author_name=_actor_name(db, actor.user_id),
            from_staff=actor.is_super_admin,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _ticket_response(ticket)


@router.patch("/tickets/{ticket_id}/status", response_model=SupportTicketResponse)
def update_status(
    ticket_id: str,
    body: UpdateSupportTicketStatusRequest,
    service: SupportService = Depends(get_support_service),
    actor: Actor = Depends(require_permission("support", "reply")),
) -> SupportTicketResponse:
    """Move a ticket across Pendientes / En curso / Completadas."""
    try:
        existing = service.get_ticket(ticket_id)
    except TicketNotFound:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    _ensure_ticket_access(service, actor, existing.client_id)
    try:
        ticket = service.set_status(ticket_id, body.status)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _ticket_response(ticket)
