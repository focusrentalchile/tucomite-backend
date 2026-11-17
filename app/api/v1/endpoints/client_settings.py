"""Building settings endpoints (profile and default voting windows)."""

from dataclasses import replace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_client_settings_service, get_current_actor, require_period_access
from app.core.database import get_db
from app.domain.client_settings import ClientSettingsRecord, InvalidVoteWindowSettings
from app.repositories.client_repository import SqlClientRepository
from app.schemas.client_settings import (
    BuildingProfileRequest,
    BuildingProfileResponse,
    VoteWindowSettingsRequest,
    VoteWindowSettingsResponse,
)
from app.services.client_settings_service import ClientSettingsService

router = APIRouter(prefix="/building-settings", tags=["building-settings"])


def _response(settings: ClientSettingsRecord) -> VoteWindowSettingsResponse:
    return VoteWindowSettingsResponse(
        high_hours=settings.vote_window_high_hours,
        medium_hours=settings.vote_window_medium_hours,
        low_hours=settings.vote_window_low_hours,
        consensus_grace_days=settings.consensus_grace_days,
    )


@router.get("/profile", response_model=BuildingProfileResponse)
def read_building_profile(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BuildingProfileResponse:
    """Return the building name and logo for the signed-in building."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    client = SqlClientRepository(db).get_client(actor.client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Building not found.")
    return BuildingProfileResponse(name=client.name, logo_url=client.logo_url or "")


@router.put("/profile", response_model=BuildingProfileResponse)
def update_building_profile(
    body: BuildingProfileRequest,
    actor: Actor = Depends(require_period_access),
    db: Session = Depends(get_db),
) -> BuildingProfileResponse:
    """Save the building name and optional logo. Owner or committee only."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    repo = SqlClientRepository(db)
    client = repo.get_client(actor.client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Building not found.")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Building name is required.")
    logo = (body.logo_url or "").strip()
    if logo and not logo.startswith("data:image/"):
        raise HTTPException(status_code=422, detail="Logo must be an image.")
    updated = replace(client, name=name, logo_url=logo)
    repo.save_client(updated)
    return BuildingProfileResponse(name=updated.name, logo_url=updated.logo_url or "")


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
            consensus_grace_days=body.consensus_grace_days,
        )
    except InvalidVoteWindowSettings as error:
        raise HTTPException(status_code=422, detail="Vote window hours are out of range.") from error
    return _response(saved)
