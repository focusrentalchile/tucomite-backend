"""Agreement endpoints for published closed-topic actas."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from sqlalchemy.orm import Session

from app.api.deps import Actor, get_agreement_service, get_db, require_permission
from app.domain.agreements import AgreementNotFound, AgreementRecord
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.client_repository import SqlClientRepository
from app.repositories.management_repository import SqlManagementRepository
from app.schemas.agreements import AgreementListResponse, AgreementResponse
from app.services.agreement_service import AgreementService
from app.services.management_service import ManagementService

router = APIRouter(tags=["agreements"])


def _response(item: AgreementRecord) -> AgreementResponse:
    return AgreementResponse(
        id=item.id,
        topic_id=item.topic_id,
        period_id=item.period_id,
        client_id=item.client_id,
        title=item.title,
        decision=item.decision,
        description=item.description,
        category_key=item.category_key,
        summary=item.summary,
        vote_yes=item.vote_yes,
        vote_no=item.vote_no,
        vote_abstain=item.vote_abstain,
        vote_result=item.vote_result,
        closed_at=item.closed_at,
        created_at=item.created_at,
        pdf_name=item.pdf_name,
    )


@router.get("/agreements", response_model=AgreementListResponse)
def list_agreements(
    client_id: str | None = Query(default=None),
    service: AgreementService = Depends(get_agreement_service),
    actor: Actor = Depends(require_permission("agreements", "view")),
    db: Session = Depends(get_db),
) -> AgreementListResponse:
    """Return published agreements visible to the actor."""
    selected = client_id
    if selected is None and actor.client_id and "management.view" not in actor.permissions:
        selected = actor.client_id
    if selected and "management.view" in actor.permissions:
        workspace = ManagementService(
            SqlManagementRepository(db),
            access=SqlAccessRepository(db),
            clients=SqlClientRepository(db),
        ).workspace_client_ids(user_id=actor.user_id, home_client_id=actor.client_id)
        if selected not in workspace:
            raise HTTPException(status_code=403, detail="That building is not in your workspace.")
    items = service.list_agreements(client_id=selected)
    if selected is None and actor.client_id and "management.view" in actor.permissions:
        workspace = ManagementService(
            SqlManagementRepository(db),
            access=SqlAccessRepository(db),
            clients=SqlClientRepository(db),
        ).workspace_client_ids(user_id=actor.user_id, home_client_id=actor.client_id)
        items = [item for item in items if item.client_id in workspace or item.client_id is None]
    elif selected is None and actor.client_id:
        items = [item for item in items if item.client_id in {actor.client_id, None}]
    return AgreementListResponse(items=[_response(item) for item in items])


@router.get("/agreements/{agreement_id}/pdf")
def download_agreement_pdf(
    agreement_id: str,
    service: AgreementService = Depends(get_agreement_service),
    _: Actor = Depends(require_permission("agreements", "view")),
) -> Response:
    """Download the branded PDF acta for one agreement."""
    try:
        agreement = service.get_agreement(agreement_id)
    except AgreementNotFound as error:
        raise HTTPException(status_code=404, detail="Agreement not found.") from error
    filename = agreement.pdf_name or "acuerdo.pdf"
    return Response(
        content=agreement.pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/agreements/{agreement_id}", response_model=AgreementResponse)
def read_agreement(
    agreement_id: str,
    service: AgreementService = Depends(get_agreement_service),
    _: Actor = Depends(require_permission("agreements", "view")),
) -> AgreementResponse:
    """Return one agreement summary."""
    try:
        agreement = service.get_agreement(agreement_id)
    except AgreementNotFound as error:
        raise HTTPException(status_code=404, detail="Agreement not found.") from error
    return _response(agreement)
