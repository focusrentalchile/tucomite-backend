"""Building settings endpoints (default voting windows)."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Actor, get_client_settings_service, get_current_actor, require_period_access
from app.domain.client_settings import ClientSettingsRecord, InvalidVoteWindowSettings
from app.schemas.client_settings import VoteWindowSettingsRequest, VoteWindowSettingsResponse
from app.services.client_settings_service import ClientSettingsService

router = APIRouter(prefix="/building-settings", tags=["building-settings"])


def _response(settings: ClientSettingsRecord) -> VoteWindowSettingsResponse:
    return VoteWindowSettingsResponse(
        high_hours=settings.vote_window_high_hours,
        medium_hours=settings.vote_window_medium_hours,
        low_hours=settings.vote_window_low_hours,
    )


@router.get("/vote-window", response_model=VoteWindowSettingsResponse)
def read_vote_window(
    service: ClientSettingsService = Depends(get_client_settings_service),
    actor: Actor = Depends(get_current_actor),
) -> VoteWindowSettingsResponse:
    """Return the default voting window hours by priority for the signed-in building."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    return _response(service.get_settings(actor.client_id))


@router.put("/vote-window", response_model=VoteWindowSettingsResponse)
def update_vote_window(
    body: VoteWindowSettingsRequest,
    service: ClientSettingsService = Depends(get_client_settings_service),
    actor: Actor = Depends(require_period_access),
) -> VoteWindowSettingsResponse:
    """Save the default voting window hours. Same access as Configuración (owner or committee)."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    try:
        saved = service.update_vote_window(
            actor.client_id,
            high_hours=body.high_hours,
            medium_hours=body.medium_hours,
            low_hours=body.low_hours,
        )
    except InvalidVoteWindowSettings as error:
        raise HTTPException(status_code=422, detail="Vote window hours are out of range.") from error
    return _response(saved)
