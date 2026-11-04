"""Period endpoints for listing and opening/closing management periods."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_db, get_period_service, require_period_access
from app.domain.periods import NoOpenPeriod, PeriodNotFound, PeriodRecord
from app.repositories.agreement_repository import SqlAgreementRepository
from app.repositories.client_repository import SqlClientRepository
from app.repositories.topic_repository import SqlTopicRepository
from app.schemas.periods import OpenPeriodRequest, PeriodListResponse, PeriodResponse
from app.services.agreement_service import AgreementService
from app.services.period_service import PeriodService

router = APIRouter(tags=["periods"])


def _period_response(period: PeriodRecord) -> PeriodResponse:
    return PeriodResponse(id=period.id, name=period.name, status=period.status)


@router.get("/periods", response_model=PeriodListResponse)
def read_periods(
    service: PeriodService = Depends(get_period_service),
    actor: Actor = Depends(require_period_access),
) -> PeriodListResponse:
    """Return periods for the signed-in building."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    return PeriodListResponse(
        items=[_period_response(period) for period in service.list_periods(actor.client_id)],
    )


@router.post("/periods", response_model=PeriodResponse, status_code=201)
def open_period(
    body: OpenPeriodRequest,
    service: PeriodService = Depends(get_period_service),
    actor: Actor = Depends(require_period_access),
) -> PeriodResponse:
    """Open (aperturar) a period. Closes any previously open period for this building."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    return _period_response(service.open_period(actor.client_id, body.name))


@router.post("/periods/{period_id}/close", response_model=PeriodResponse)
def close_period(
    period_id: str,
    service: PeriodService = Depends(get_period_service),
    actor: Actor = Depends(require_period_access),
    db: Session = Depends(get_db),
) -> PeriodResponse:
    """Close an open period and publish closed topics into Acuerdos."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    try:
        closed = service.close_period(actor.client_id, period_id)
    except PeriodNotFound as error:
        raise HTTPException(status_code=404, detail="Period not found.") from error
    except NoOpenPeriod as error:
        raise HTTPException(status_code=409, detail="Period is not open.") from error
    AgreementService(
        SqlAgreementRepository(db),
        SqlTopicRepository(db),
        SqlClientRepository(db),
    ).publish_closed_topics_for_period(period_id, client_id=actor.client_id)
    return _period_response(closed)
