"""Period endpoints. Only committee members may use them."""

from fastapi import APIRouter, Depends

from app.api.deps import Actor, get_period_service, require_committee_member
from app.domain.periods import PeriodRecord
from app.schemas.periods import OpenPeriodRequest, PeriodListResponse, PeriodResponse
from app.services.period_service import PeriodService

router = APIRouter(tags=["periods"])


def _period_response(period: PeriodRecord) -> PeriodResponse:
    return PeriodResponse(id=period.id, name=period.name, status=period.status)


@router.get("/periods", response_model=PeriodListResponse)
def read_periods(
    service: PeriodService = Depends(get_period_service),
    _: Actor = Depends(require_committee_member),
) -> PeriodListResponse:
    """Return every period. Only committee members may look."""
    return PeriodListResponse(items=[_period_response(period) for period in service.list_periods()])


@router.post("/periods", response_model=PeriodResponse, status_code=201)
def open_period(
    body: OpenPeriodRequest,
    service: PeriodService = Depends(get_period_service),
    _: Actor = Depends(require_committee_member),
) -> PeriodResponse:
    """Open (aperturar) a period. Closes any previously open period."""
    return _period_response(service.open_period(body.name))
