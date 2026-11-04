"""Legal case endpoints for committee and building owners."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_db, require_permission
from app.domain.legal import LegalCaseAttachmentRecord, LegalCaseNotFound, LegalCaseRecord
from app.repositories.legal_repository import SqlLegalRepository
from app.schemas.legal import (
    CreateLegalCaseRequest,
    LegalCaseAttachmentResponse,
    LegalCaseListResponse,
    LegalCaseResponse,
    UpdateLegalCaseRequest,
)
from app.services.legal_service import LegalService

router = APIRouter(tags=["legal"])


def _attachment(item: LegalCaseAttachmentRecord) -> LegalCaseAttachmentResponse:
    kind = item.kind if item.kind in {"image", "video", "file"} else "file"
    return LegalCaseAttachmentResponse(id=item.id, kind=kind, name=item.name, url=item.url)  # type: ignore[arg-type]


def _case_response(
    case: LegalCaseRecord,
    attachments: list[LegalCaseAttachmentRecord],
) -> LegalCaseResponse:
    return LegalCaseResponse(
        id=case.id,
        title=case.title,
        description=case.description,
        created_at=case.created_at,
        attachments=[_attachment(item) for item in attachments],
    )


@router.get("/legal-cases", response_model=LegalCaseListResponse)
def read_legal_cases(
    actor: Actor = Depends(require_permission("legal", "view")),
    db: Session = Depends(get_db),
) -> LegalCaseListResponse:
    """Return legal cases for the signed-in building."""
    if not actor.client_id:
        return LegalCaseListResponse(items=[])
    service = LegalService(SqlLegalRepository(db))
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
    """Create a legal case with optional attachments."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    service = LegalService(SqlLegalRepository(db))
    case = service.create_case(
        client_id=actor.client_id,
        created_by_user_id=actor.user_id,
        title=body.title,
        description=body.description,
        attachments=[item.model_dump() for item in body.attachments],
    )
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
    service = LegalService(SqlLegalRepository(db))
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


@router.delete("/legal-cases/{case_id}", status_code=204)
def delete_legal_case(
    case_id: str,
    actor: Actor = Depends(require_permission("legal", "view")),
    db: Session = Depends(get_db),
) -> None:
    """Delete a legal case that belongs to the building."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    service = LegalService(SqlLegalRepository(db))
    try:
        service.delete_case(case_id, client_id=actor.client_id)
    except LegalCaseNotFound as error:
        raise HTTPException(status_code=404, detail="Legal case not found.") from error
