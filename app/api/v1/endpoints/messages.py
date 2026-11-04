"""Resident message endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_current_actor, require_permission
from app.core.database import get_db
from app.domain.messages import InvalidMessageStatus, MessageNotFound, MessageTypeNotFound
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.message_repository import SqlMessageRepository
from app.repositories.period_repository import SqlPeriodRepository
from app.repositories.topic_repository import SqlTopicRepository
from app.schemas.messages import (
    AppealMessageRequest,
    CreateMessageReplyRequest,
    CreateMessageRequest,
    MessageAttachmentResponse,
    MessageListResponse,
    MessageReplyResponse,
    MessageResponse,
    MessageStatusEventResponse,
    MessageTypeListResponse,
    MessageTypeResponse,
    UpdateMessageRequest,
    UpdateMessageStatusRequest,
)
from app.services.message_service import MessageService
from app.services.topic_service import TopicService

router = APIRouter(tags=["messages"])


def get_message_service(db: Session = Depends(get_db)) -> MessageService:
    """Build the message service for one request."""
    return MessageService(
        SqlMessageRepository(db),
        topic_service=TopicService(SqlTopicRepository(db)),
    )


def _attachment(item) -> MessageAttachmentResponse:
    return MessageAttachmentResponse(id=item.id, kind=item.kind, name=item.name, url=item.url)


def _reply(item) -> MessageReplyResponse:
    return MessageReplyResponse(
        id=item.id,
        message_id=item.message_id,
        author_user_id=item.author_user_id,
        author_name=item.author_name,
        body=item.body,
        from_admin=item.from_admin,
        created_at=item.created_at,
        attachments=[_attachment(file) for file in item.attachments],
    )


def _event(item) -> MessageStatusEventResponse:
    return MessageStatusEventResponse(
        id=item.id,
        message_id=item.message_id,
        status=item.status,
        occurred_at=item.occurred_at,
    )


def _message(item) -> MessageResponse:
    return MessageResponse(
        id=item.id,
        client_id=item.client_id,
        author_user_id=item.author_user_id,
        author_name=item.author_name,
        message_type_id=item.message_type_id,
        message_type_name=item.message_type_name,
        subject=item.subject,
        body=item.body,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
        sent_at=item.sent_at,
        seen_at=item.seen_at,
        in_resolution_at=item.in_resolution_at,
        finished_at=item.finished_at,
        parent_message_id=item.parent_message_id,
        topic_id=item.topic_id,
        attachments=[_attachment(file) for file in item.attachments],
        replies=[_reply(reply) for reply in item.replies],
        status_events=[_event(event) for event in item.status_events],
    )


@router.get("/message-types", response_model=MessageTypeListResponse)
def list_message_types(
    service: MessageService = Depends(get_message_service),
    _: Actor = Depends(get_current_actor),
) -> MessageTypeListResponse:
    """Return message types ordered alphabetically."""
    return MessageTypeListResponse(
        items=[MessageTypeResponse(id=item.id, name=item.name) for item in service.list_types()],
    )


@router.get("/messages", response_model=MessageListResponse)
def list_messages(
    client_id: str | None = Query(default=None),
    service: MessageService = Depends(get_message_service),
    actor: Actor = Depends(get_current_actor),
) -> MessageListResponse:
    """List messages for the resident author or a building administrator."""
    held = set(actor.permissions)
    if "messages.manage" in held and client_id:
        items = service.list_for_client(client_id)
    elif "messages.manage" in held and actor.client_id:
        items = service.list_for_client(actor.client_id)
    elif "messages.view" in held:
        items = service.list_for_author(actor.user_id)
    else:
        raise HTTPException(status_code=403, detail="Forbidden.")
    return MessageListResponse(items=[_message(item) for item in items])


@router.post("/messages", response_model=MessageResponse, status_code=201)
def create_message(
    body: CreateMessageRequest,
    service: MessageService = Depends(get_message_service),
    actor: Actor = Depends(require_permission("messages", "create")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Resident opens a new message ticket."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    access = SqlAccessRepository(db)
    user = access.get_user(actor.user_id)
    try:
        record = service.create(
            client_id=actor.client_id,
            author_user_id=actor.user_id,
            author_name=user.full_name if user else "",
            message_type_id=body.message_type_id,
            subject=body.subject,
            body=body.body,
            attachments=[item.model_dump() for item in body.attachments],
        )
    except MessageTypeNotFound as error:
        raise HTTPException(status_code=404, detail="Message type not found.") from error
    return _message(record)


@router.get("/messages/{message_id}", response_model=MessageResponse)
def read_message(
    message_id: str,
    service: MessageService = Depends(get_message_service),
    actor: Actor = Depends(get_current_actor),
) -> MessageResponse:
    """Load one message when the actor may see it."""
    try:
        record = service.get(message_id)
    except MessageNotFound as error:
        raise HTTPException(status_code=404, detail="Message not found.") from error
    held = set(actor.permissions)
    if "messages.manage" in held:
        return _message(record)
    if "messages.view" in held and record.author_user_id == actor.user_id:
        return _message(record)
    raise HTTPException(status_code=403, detail="Forbidden.")


@router.patch("/messages/{message_id}", response_model=MessageResponse)
def update_message(
    message_id: str,
    body: UpdateMessageRequest,
    service: MessageService = Depends(get_message_service),
    actor: Actor = Depends(require_permission("messages", "update")),
) -> MessageResponse:
    """Resident edits a still-sent message."""
    try:
        record = service.update(
            message_id,
            author_user_id=actor.user_id,
            message_type_id=body.message_type_id,
            subject=body.subject,
            body=body.body,
            attachments=[item.model_dump() for item in body.attachments],
        )
    except MessageNotFound as error:
        raise HTTPException(status_code=404, detail="Message not found.") from error
    except MessageTypeNotFound as error:
        raise HTTPException(status_code=404, detail="Message type not found.") from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except InvalidMessageStatus as error:
        raise HTTPException(status_code=409, detail="Only sent messages can be edited.") from error
    return _message(record)


@router.delete("/messages/{message_id}", status_code=204)
def delete_message(
    message_id: str,
    service: MessageService = Depends(get_message_service),
    actor: Actor = Depends(require_permission("messages", "delete")),
) -> None:
    """Resident deletes a still-sent message."""
    try:
        service.delete(message_id, author_user_id=actor.user_id)
    except MessageNotFound as error:
        raise HTTPException(status_code=404, detail="Message not found.") from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except InvalidMessageStatus as error:
        raise HTTPException(status_code=409, detail="Only sent messages can be deleted.") from error


@router.post("/messages/{message_id}/open", response_model=MessageResponse)
def open_message(
    message_id: str,
    service: MessageService = Depends(get_message_service),
    _: Actor = Depends(require_permission("messages", "manage")),
) -> MessageResponse:
    """Administrator opens a card; Enviado becomes Visto."""
    try:
        return _message(service.open_by_admin(message_id))
    except MessageNotFound as error:
        raise HTTPException(status_code=404, detail="Message not found.") from error


@router.post("/messages/{message_id}/status", response_model=MessageResponse)
def update_message_status(
    message_id: str,
    body: UpdateMessageStatusRequest,
    service: MessageService = Depends(get_message_service),
    _: Actor = Depends(require_permission("messages", "manage")),
) -> MessageResponse:
    """Administrator moves the card to En resolución or Finalizada."""
    try:
        return _message(service.set_status(message_id, body.status))
    except MessageNotFound as error:
        raise HTTPException(status_code=404, detail="Message not found.") from error
    except InvalidMessageStatus as error:
        raise HTTPException(status_code=409, detail="Invalid status transition.") from error


@router.post("/messages/{message_id}/replies", response_model=MessageResponse)
def create_message_reply(
    message_id: str,
    body: CreateMessageReplyRequest,
    service: MessageService = Depends(get_message_service),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Post a reply on the thread."""
    held = set(actor.permissions)
    from_admin = "messages.manage" in held
    if not from_admin and "messages.view" not in held:
        raise HTTPException(status_code=403, detail="Forbidden.")
    access = SqlAccessRepository(db)
    user = access.get_user(actor.user_id)
    try:
        current = service.get(message_id)
        if not from_admin and current.author_user_id != actor.user_id:
            raise HTTPException(status_code=403, detail="Forbidden.")
        record = service.add_reply(
            message_id,
            author_user_id=actor.user_id,
            author_name=user.full_name if user else "",
            body=body.body,
            from_admin=from_admin,
            attachments=[item.model_dump() for item in body.attachments],
        )
    except MessageNotFound as error:
        raise HTTPException(status_code=404, detail="Message not found.") from error
    return _message(record)


@router.post("/messages/{message_id}/appeal", response_model=MessageResponse, status_code=201)
def appeal_message(
    message_id: str,
    body: AppealMessageRequest,
    service: MessageService = Depends(get_message_service),
    actor: Actor = Depends(require_permission("messages", "create")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Appeal a finished message: open a Tema and a new Enviado ticket."""
    access = SqlAccessRepository(db)
    user = access.get_user(actor.user_id)
    period_id = None
    try:
        open_period = SqlPeriodRepository(db).get_open_period()
        period_id = open_period.id if open_period else None
    except Exception:
        period_id = None
    try:
        record = service.appeal(
            message_id,
            author_user_id=actor.user_id,
            author_name=user.full_name if user else "",
            body=body.body,
            attachments=[item.model_dump() for item in body.attachments],
            period_id=period_id,
        )
    except MessageNotFound as error:
        raise HTTPException(status_code=404, detail="Message not found.") from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except InvalidMessageStatus as error:
        raise HTTPException(status_code=409, detail="Only finished messages can be appealed.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _message(record)
