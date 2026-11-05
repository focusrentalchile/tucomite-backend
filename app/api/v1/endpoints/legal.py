"""Legal case endpoints for committee, building owners, and legal counsel."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_db, require_permission
from app.domain.legal import (
    InvalidLegalStatus,
    LegalCaseAttachmentRecord,
    LegalCaseMessageRecord,
    LegalCaseNotFound,
    LegalCaseRecord,
)
from app.domain.notifications import NotificationRecord
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.legal_repository import SqlLegalRepository
from app.repositories.notification_repository import SqlNotificationRepository
from app.schemas.legal import (
    CreateLegalCaseMessageRequest,
    CreateLegalCaseRequest,
    LegalCaseAttachmentResponse,
    LegalCaseListResponse,
    LegalCaseMessageResponse,
    LegalCaseResponse,
    SetLegalCaseStatusRequest,
    UpdateLegalCaseRequest,
)
from app.services.legal_service import LegalService

router = APIRouter(tags=["legal"])


def _attachment(item: LegalCaseAttachmentRecord) -> LegalCaseAttachmentResponse:
    kind = item.kind if item.kind in {"image", "video", "file"} else "file"
    return LegalCaseAttachmentResponse(id=item.id, kind=kind, name=item.name, url=item.url)  # type: ignore[arg-type]


def _message(item: LegalCaseMessageRecord) -> LegalCaseMessageResponse:
    return LegalCaseMessageResponse(
        id=item.id,
        author_user_id=item.author_user_id,
        author_name=item.author_name,
        body=item.body,
        from_legal=item.from_legal,
        created_at=item.created_at,
    )


def _case_response(
    case: LegalCaseRecord,
    attachments: list[LegalCaseAttachmentRecord],
    messages: list[LegalCaseMessageRecord] | None = None,
) -> LegalCaseResponse:
    status = case.status if case.status in {"waiting", "in_progress", "finished"} else "waiting"
    return LegalCaseResponse(
        id=case.id,
        title=case.title,
        description=case.description,
        status=status,  # type: ignore[arg-type]
        created_at=case.created_at,
        attachments=[_attachment(item) for item in attachments],
        messages=[_message(item) for item in (messages or [])],
    )


def _service(db: Session) -> LegalService:
    return LegalService(SqlLegalRepository(db))


def _notify_legal_counsel(db: Session, *, client_id: str, case: LegalCaseRecord) -> None:
    """Send an in-app notice to every legal user in the building."""
    access = SqlAccessRepository(db)
    roles = {role.name: role.id for role in access.list_roles()}
    legal_role_id = roles.get("legal")
    if not legal_role_id:
        return
    notifications = SqlNotificationRepository(db)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for user in access.list_users():
        if user.client_id != client_id or user.role_id != legal_role_id:
            continue
        notifications.add(
            NotificationRecord(
                id=str(uuid4()),
                user_id=user.id,
                kind="legal_case_created",
                title="Nueva cotización de asesoría legal",
                body=f"Se solicitó «{case.title}». Revisalo en Casos (En espera).",
                created_at=now,
                read_at=None,
            ),
        )


@router.get("/legal-cases", response_model=LegalCaseListResponse)
def read_legal_cases(
    actor: Actor = Depends(require_permission("legal", "view")),
    db: Session = Depends(get_db),
) -> LegalCaseListResponse:
    """Return legal cases for the signed-in building."""
    if not actor.client_id:
        return LegalCaseListResponse(items=[])
    service = _service(db)
    cases = service.list_cases(actor.client_id)
    by_case: dict[str, list[LegalCaseAttachmentRecord]] = {case.id: [] for case in cases}
    for item in service.list_attachments_for_cases([case.id for case in cases]):
        by_case.setdefault(item.case_id, []).append(item)
    return LegalCaseListResponse(
        items=[_case_response(case, by_case.get(case.id, [])) for case in cases],
    )


@router.post("/legal-cases", response_model=LegalCaseResponse, status_code=201)
def create_legal_case(
    body: CreateLegalCaseRequest,
    actor: Actor = Depends(require_permission("legal", "view")),
    db: Session = Depends(get_db),
) -> LegalCaseResponse:
    """Create a legal case with optional attachments (client / committee)."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    service = _service(db)
    case = service.create_case(
        client_id=actor.client_id,
        created_by_user_id=actor.user_id,
        title=body.title,
        description=body.description,
        attachments=[item.model_dump() for item in body.attachments],
    )
    _notify_legal_counsel(db, client_id=actor.client_id, case=case)
    stored = service.list_attachments_for_cases([case.id])
    return _case_response(case, stored)


@router.patch("/legal-cases/{case_id}", response_model=LegalCaseResponse)
def update_legal_case(
    case_id: str,
    body: UpdateLegalCaseRequest,
    actor: Actor = Depends(require_permission("legal", "view")),
    db: Session = Depends(get_db),
) -> LegalCaseResponse:
    """Update a legal case that belongs to the building."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    service = _service(db)
    try:
        case = service.update_case(
            case_id,
            client_id=actor.client_id,
            title=body.title,
            description=body.description,
            attachments=[item.model_dump() for item in body.attachments],
        )
    except LegalCaseNotFound as error:
        raise HTTPException(status_code=404, detail="Legal case not found.") from error
    stored = service.list_attachments_for_cases([case.id])
    return _case_response(case, stored)


@router.post("/legal-cases/{case_id}/open", response_model=LegalCaseResponse)
def open_legal_case(
    case_id: str,
    actor: Actor = Depends(require_permission("legal", "reply")),
    db: Session = Depends(get_db),
) -> LegalCaseResponse:
    """Open a case for counsel work (moves En espera → En proceso)."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    service = _service(db)
    try:
        case = service.open_case(case_id, client_id=actor.client_id)
        messages = service.list_messages(case_id, client_id=actor.client_id)
    except LegalCaseNotFound as error:
        raise HTTPException(status_code=404, detail="Legal case not found.") from error
    stored = service.list_attachments_for_cases([case.id])
    return _case_response(case, stored, messages)


@router.patch("/legal-cases/{case_id}/status", response_model=LegalCaseResponse)
def set_legal_case_status(
    case_id: str,
    body: SetLegalCaseStatusRequest,
    actor: Actor = Depends(require_permission("legal", "update")),
    db: Session = Depends(get_db),
) -> LegalCaseResponse:
    """Move a case between board columns."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    service = _service(db)
    try:
        case = service.set_status(case_id, client_id=actor.client_id, status=body.status)
    except LegalCaseNotFound as error:
        raise HTTPException(status_code=404, detail="Legal case not found.") from error
    except InvalidLegalStatus as error:
        raise HTTPException(status_code=422, detail="Invalid status.") from error
    stored = service.list_attachments_for_cases([case.id])
    return _case_response(case, stored)


@router.get("/legal-cases/{case_id}/messages", response_model=list[LegalCaseMessageResponse])
def read_legal_case_messages(
    case_id: str,
    actor: Actor = Depends(require_permission("legal", "view")),
    db: Session = Depends(get_db),
) -> list[LegalCaseMessageResponse]:
    """Return the message thread for one case."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    service = _service(db)
    try:
        messages = service.list_messages(case_id, client_id=actor.client_id)
    except LegalCaseNotFound as error:
        raise HTTPException(status_code=404, detail="Legal case not found.") from error
    return [_message(item) for item in messages]


@router.post(
    "/legal-cases/{case_id}/messages",
    response_model=LegalCaseResponse,
    status_code=201,
)
def create_legal_case_message(
    case_id: str,
    body: CreateLegalCaseMessageRequest,
    actor: Actor = Depends(require_permission("legal", "reply")),
    db: Session = Depends(get_db),
) -> LegalCaseResponse:
    """Post a counsel message and move the case to En proceso when needed."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    access = SqlAccessRepository(db)
    user = access.get_user(actor.user_id)
    service = _service(db)
    try:
        case, _ = service.add_message(
            case_id,
            client_id=actor.client_id,
            author_user_id=actor.user_id,
            author_name=user.full_name if user else "",
            body=body.body,
            from_legal=True,
        )
        messages = service.list_messages(case_id, client_id=actor.client_id)
    except LegalCaseNotFound as error:
        raise HTTPException(status_code=404, detail="Legal case not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    stored = service.list_attachments_for_cases([case.id])
    return _case_response(case, stored, messages)


@router.delete("/legal-cases/{case_id}", status_code=204)
def delete_legal_case(
    case_id: str,
    actor: Actor = Depends(require_permission("legal", "view")),
    db: Session = Depends(get_db),
) -> None:
    """Delete a legal case that belongs to the building."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    service = _service(db)
    try:
        service.delete_case(case_id, client_id=actor.client_id)
    except LegalCaseNotFound as error:
        raise HTTPException(status_code=404, detail="Legal case not found.") from error
