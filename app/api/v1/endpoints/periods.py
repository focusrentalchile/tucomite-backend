"""Period endpoints for listing and opening/closing management periods."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Actor, get_period_service, require_period_access
from app.domain.periods import NoOpenPeriod, PeriodNotFound, PeriodRecord
from app.schemas.periods import OpenPeriodRequest, PeriodListResponse, PeriodResponse
from app.services.period_service import PeriodService

router = APIRouter(tags=["periods"])


def _period_response(period: PeriodRecord) -> PeriodResponse:
    return PeriodResponse(id=period.id, name=period.name, status=period.status)


@router.get("/periods", response_model=PeriodListResponse)
def read_periods(
    service: PeriodService = Depends(get_period_service),
    _: Actor = Depends(require_period_access),
) -> PeriodListResponse:
    """Return every period."""
    return PeriodListResponse(items=[_period_response(period) for period in service.list_periods()])


@router.post("/periods", response_model=PeriodResponse, status_code=201)
def open_period(
    body: OpenPeriodRequest,
    service: PeriodService = Depends(get_period_service),
    _: Actor = Depends(require_period_access),
) -> PeriodResponse:
    """Open (aperturar) a period. Closes any previously open period."""
    return _period_response(service.open_period(body.name))


@router.post("/periods/{period_id}/close", response_model=PeriodResponse)
def close_period(
    period_id: str,
    service: PeriodService = Depends(get_period_service),
    _: Actor = Depends(require_period_access),
) -> PeriodResponse:
    """Close an open period."""
    try:
        return _period_response(service.close_period(period_id))
    except PeriodNotFound as error:
        raise HTTPException(status_code=404, detail="Period not found.") from error
    except NoOpenPeriod as error:
        raise HTTPException(status_code=409, detail="Period is not open.") from error
