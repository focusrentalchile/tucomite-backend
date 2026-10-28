"""Platform support ticket endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import Actor, require_permission
from app.core.database import get_db
from app.domain.support import TicketNotFound
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.client_repository import SqlClientRepository
from app.repositories.support_repository import SqlSupportRepository
from app.schemas.support import (
    CreateSupportMessageRequest,
    CreateSupportTicketRequest,
    SupportMessageResponse,
    SupportTicketListResponse,
    SupportTicketResponse,
    UpdateSupportTicketStatusRequest,
)
from app.services.support_service import SupportService

router = APIRouter(prefix="/support", tags=["support"])


def get_support_service(db: Session = Depends(get_db)) -> SupportService:
    """Build a support service for the request."""
    return SupportService(SqlSupportRepository(db))


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


def _actor_name(db: Session, user_id: str) -> str:
    user = SqlAccessRepository(db).get_user(user_id)
    return user.full_name if user is not None else ""


def _client_name(db: Session, client_id: str | None) -> str:
    if not client_id:
        return ""
    client = SqlClientRepository(db).get_client(client_id)
    return client.name if client is not None else ""


def _ensure_ticket_access(actor: Actor, ticket_client_id: str | None) -> None:
    if actor.is_super_admin:
        return
    if not actor.client_id or actor.client_id != ticket_client_id:
        raise HTTPException(status_code=404, detail="Ticket not found.")


@router.get("/tickets", response_model=SupportTicketListResponse)
def list_tickets(
    service: SupportService = Depends(get_support_service),
    actor: Actor = Depends(require_permission("support", "view")),
) -> SupportTicketListResponse:
    """List tickets for the actor's building, or every ticket for staff."""
    client_id = None if actor.is_super_admin else actor.client_id
    if not actor.is_super_admin and not client_id:
        return SupportTicketListResponse(items=[])
    tickets = service.list_tickets(client_id=client_id)
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
    _ensure_ticket_access(actor, ticket.client_id)
    return _ticket_response(ticket)


@router.post("/tickets", response_model=SupportTicketResponse, status_code=201)
def create_ticket(
    body: CreateSupportTicketRequest,
    service: SupportService = Depends(get_support_service),
    actor: Actor = Depends(require_permission("support", "create")),
    db: Session = Depends(get_db),
) -> SupportTicketResponse:
    """Open a support ticket for the signed-in building."""
    if actor.is_super_admin:
        raise HTTPException(status_code=403, detail="Staff replies on existing tickets.")
    if not actor.client_id:
        raise HTTPException(status_code=403, detail="Forbidden.")
    try:
        ticket = service.create_ticket(
            subject=body.subject,
            body=body.body,
            created_by_user_id=actor.user_id,
            created_by_name=_actor_name(db, actor.user_id),
            client_id=actor.client_id,
            client_name=_client_name(db, actor.client_id),
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
    _ensure_ticket_access(actor, existing.client_id)
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
    _ensure_ticket_access(actor, existing.client_id)
    try:
        ticket = service.set_status(ticket_id, body.status)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _ticket_response(ticket)
