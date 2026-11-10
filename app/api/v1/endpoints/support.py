"""Platform support ticket endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_current_actor, get_db, require_permission, require_super_admin
from app.core.config import settings
from app.domain.support import (
    InvalidSupportType,
    SupportEmailError,
    SupportTicketNotFound,
    SupportTypeNotFound,
)
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.platform_settings_repository import SqlPlatformSettingsRepository
from app.repositories.support_repository import SqlSupportRepository
from app.schemas.support import (
    CreateSupportReplyRequest,
    UpdateSupportReplyRequest,
    CreateSupportTicketRequest,
    SupportAttachmentResponse,
    SupportReplyResponse,
    SupportTicketListResponse,
    SupportTicketResponse,
    SupportTypeListResponse,
    SupportTypeResponse,
)
from app.services.email_service import SmtpDeliveryConfig
from app.services.platform_settings_service import PlatformSettingsService
from app.services.support_service import SupportService

router = APIRouter(prefix="/support", tags=["support"])


def get_support_service(db: Session = Depends(get_db)) -> SupportService:
    """Build a support service bound to the request session."""
    return SupportService(SqlSupportRepository(db))


def _ticket_response(ticket) -> SupportTicketResponse:
    return SupportTicketResponse(
        id=ticket.id,
        client_id=ticket.client_id,
        author_user_id=ticket.author_user_id,
        author_name=ticket.author_name,
        support_type_id=ticket.support_type_id,
        support_type_name=ticket.support_type_name,
        subject=ticket.subject,
        body=ticket.body,
        status=ticket.status,
        contact_name=ticket.contact_name,
        contact_email=ticket.contact_email,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        attachments=[
            SupportAttachmentResponse(
                id=item.id,
                kind=item.kind,  # type: ignore[arg-type]
                name=item.name,
                url=item.url,
            )
            for item in ticket.attachments
        ],
        replies=[
            SupportReplyResponse(
                id=item.id,
                ticket_id=item.ticket_id,
                author_user_id=item.author_user_id,
                author_name=item.author_name,
                body=item.body,
                from_staff=item.from_staff,
                created_at=item.created_at,
            )
            for item in ticket.replies
        ],
    )


def _actor_display_name(db: Session, user_id: str) -> str:
    user = SqlAccessRepository(db).get_user(user_id)
    if user is None:
        return "Usuario"
    return user.full_name or user.email or "Usuario"


@router.get("/types", response_model=SupportTypeListResponse)
def list_support_types(
    creatable_only: bool = False,
    actor: Actor = Depends(get_current_actor),
    service: SupportService = Depends(get_support_service),
) -> SupportTypeListResponse:
    """List support types; buildings only see creatable ones when requested."""
    _ = actor
    items = service.list_types(creatable_only=creatable_only)
    return SupportTypeListResponse(items=[SupportTypeResponse(id=i.id, name=i.name) for i in items])


@router.get("/tickets", response_model=SupportTicketListResponse)
def list_support_tickets(
    actor: Actor = Depends(get_current_actor),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketListResponse:
    """Super admin sees all tickets; buildings see their own."""
    if actor.is_super_admin:
        items = service.list_for_super_admin()
    elif "support.view" in actor.permissions:
        if not actor.client_id:
            raise HTTPException(status_code=403, detail="Forbidden.")
        items = service.list_for_client(actor.client_id)
    else:
        raise HTTPException(status_code=403, detail="Forbidden.")
    return SupportTicketListResponse(items=[_ticket_response(item) for item in items])


@router.post("/tickets", response_model=SupportTicketResponse, status_code=201)
def create_support_ticket(
    body: CreateSupportTicketRequest,
    actor: Actor = Depends(require_permission("support", "create")),
    db: Session = Depends(get_db),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketResponse:
    """Open a Soporte ticket for the signed-in building (Asunto + Mensaje only)."""
    if actor.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin cannot open building tickets.")
    if not actor.client_id:
        raise HTTPException(status_code=403, detail="Building context required.")
    try:
        created = service.create_building_ticket(
            client_id=actor.client_id,
            author_user_id=actor.user_id,
            author_name=_actor_display_name(db, actor.user_id),
            subject=body.subject,
            body=body.body,
            support_type_id=body.support_type_id,
            attachments=[item.model_dump() for item in body.attachments],
        )
    except SupportTypeNotFound as error:
        raise HTTPException(status_code=404, detail="Support type not found.") from error
    except InvalidSupportType as error:
        raise HTTPException(status_code=422, detail="Invalid support type.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _ticket_response(created)


@router.get("/tickets/{ticket_id}", response_model=SupportTicketResponse)
def read_support_ticket(
    ticket_id: str,
    actor: Actor = Depends(get_current_actor),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketResponse:
    """Read one ticket when the actor may see it."""
    try:
        ticket = service.get(ticket_id)
    except SupportTicketNotFound as error:
        raise HTTPException(status_code=404, detail="Support ticket not found.") from error
    if actor.is_super_admin:
        return _ticket_response(ticket)
    if "support.view" not in actor.permissions:
        raise HTTPException(status_code=403, detail="Forbidden.")
    if ticket.client_id != actor.client_id:
        raise HTTPException(status_code=403, detail="Forbidden.")
    return _ticket_response(ticket)


@router.post("/tickets/{ticket_id}/replies", response_model=SupportTicketResponse, status_code=201)
def create_support_reply(
    ticket_id: str,
    body: CreateSupportReplyRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketResponse:
    """Append a chat reply. Staff replies require super admin."""
    try:
        ticket = service.get(ticket_id)
    except SupportTicketNotFound as error:
        raise HTTPException(status_code=404, detail="Support ticket not found.") from error

    from_staff = False
    if actor.is_super_admin:
        from_staff = True
    elif "support.view" in actor.permissions and ticket.client_id == actor.client_id:
        from_staff = False
    else:
        raise HTTPException(status_code=403, detail="Forbidden.")

    if from_staff:
        require_super_admin(actor)

    platform = PlatformSettingsService(SqlPlatformSettingsRepository(db)).get_settings()
    site_url = platform.public_site_url.strip() or settings.public_site_url
    smtp = SmtpDeliveryConfig(
        host=platform.smtp_host,
        port=platform.smtp_port,
        user=platform.smtp_user,
        password=platform.smtp_password,
        from_address=platform.smtp_from,
        use_tls=platform.smtp_use_tls,
    )
    try:
        updated = service.add_reply(
            ticket_id,
            author_user_id=actor.user_id,
            author_name=_actor_display_name(db, actor.user_id),
            body=body.body,
            from_staff=from_staff,
            site_url=site_url,
            smtp=smtp,
        )
    except SupportTicketNotFound as error:
        raise HTTPException(status_code=404, detail="Support ticket not found.") from error
    except SupportEmailError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _ticket_response(updated)


@router.patch("/tickets/{ticket_id}/replies/{reply_id}", response_model=SupportTicketResponse)
def update_support_reply(
    ticket_id: str,
    reply_id: str,
    body: UpdateSupportReplyRequest,
    actor: Actor = Depends(get_current_actor),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketResponse:
    """Edit a chat reply owned by the actor (or any reply if super admin)."""
    try:
        ticket = service.get(ticket_id)
    except SupportTicketNotFound as error:
        raise HTTPException(status_code=404, detail="Support ticket not found.") from error

    if not actor.is_super_admin:
        if "support.view" not in actor.permissions or ticket.client_id != actor.client_id:
            raise HTTPException(status_code=403, detail="Forbidden.")

    try:
        updated = service.update_reply(
            ticket_id,
            reply_id,
            body=body.body,
            actor_user_id=actor.user_id,
            is_super_admin=actor.is_super_admin,
        )
    except SupportTicketNotFound as error:
        raise HTTPException(status_code=404, detail="Support ticket not found.") from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail="Forbidden.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _ticket_response(updated)


@router.delete("/tickets/{ticket_id}/replies/{reply_id}", response_model=SupportTicketResponse)
def delete_support_reply(
    ticket_id: str,
    reply_id: str,
    actor: Actor = Depends(get_current_actor),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketResponse:
    """Delete a chat reply owned by the actor (or any reply if super admin)."""
    try:
        ticket = service.get(ticket_id)
    except SupportTicketNotFound as error:
        raise HTTPException(status_code=404, detail="Support ticket not found.") from error

    if not actor.is_super_admin:
        if "support.view" not in actor.permissions or ticket.client_id != actor.client_id:
            raise HTTPException(status_code=403, detail="Forbidden.")

    try:
        updated = service.delete_reply(
            ticket_id,
            reply_id,
            actor_user_id=actor.user_id,
            is_super_admin=actor.is_super_admin,
        )
    except SupportTicketNotFound as error:
        raise HTTPException(status_code=404, detail="Support ticket not found.") from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail="Forbidden.") from error
    return _ticket_response(updated)
