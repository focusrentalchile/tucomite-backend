"""Invitation endpoints for super admin, building owners, and public accept."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_current_actor, get_db, require_super_admin
from app.domain.access import DuplicateEmail
from app.domain.invitations import (
    KIND_PLATFORM,
    InvitationAlreadyUsed,
    InvitationEmailFailed,
    InvitationForbidden,
    InvitationNotFound,
)
from app.schemas.invitations import (
    AcceptBuildingInvitationRequest,
    AcceptPlatformInvitationRequest,
    CreateBuildingInvitationRequest,
    CreatePlatformInvitationRequest,
    InvitationListResponse,
    InvitationResponse,
    PublicInvitationResponse,
)
from app.services.invitation_service import InvitationService, get_invitation_service, tracking_pixel_bytes

router = APIRouter(prefix="/invitations", tags=["invitations"])


def _response(record) -> InvitationResponse:
    return InvitationResponse(
        id=record.id,
        kind=record.kind,
        name=record.name,
        email=record.email,
        building_name=record.building_name,
        role_key=record.role_key,
        client_id=record.client_id,
        status=record.status,
        sent_at=record.sent_at,
        opened_at=record.opened_at,
        registered_at=record.registered_at,
        created_at=record.created_at,
    )


def _service(db: Session = Depends(get_db)) -> InvitationService:
    return get_invitation_service(db)


@router.get("", response_model=InvitationListResponse)
def list_invitations(
    actor: Actor = Depends(get_current_actor),
    service: InvitationService = Depends(_service),
) -> InvitationListResponse:
    """List invitations visible to the signed-in actor."""
    if not actor.is_super_admin and "users.create" not in actor.permissions:
        raise HTTPException(status_code=403, detail="Forbidden.")
    items = service.list_for_actor(is_super_admin=actor.is_super_admin, client_id=actor.client_id)
    return InvitationListResponse(items=[_response(item) for item in items])


@router.post("/platform", response_model=InvitationResponse, status_code=201)
def create_platform_invitation(
    body: CreatePlatformInvitationRequest,
    _: object = Depends(require_super_admin),
    actor: Actor = Depends(get_current_actor),
    service: InvitationService = Depends(_service),
) -> InvitationResponse:
    """Super-admin invite with name + email only."""
    try:
        record, _result = service.create_platform(
            name=body.name,
            email=body.email,
            invited_by_user_id=actor.user_id,
        )
    except DuplicateEmail as error:
        raise HTTPException(status_code=409, detail="Email already registered.") from error
    except InvitationEmailFailed as error:
        raise HTTPException(status_code=502, detail=error.message) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _response(record)


@router.post("/building", response_model=InvitationResponse, status_code=201)
def create_building_invitation(
    body: CreateBuildingInvitationRequest,
    actor: Actor = Depends(get_current_actor),
    service: InvitationService = Depends(_service),
) -> InvitationResponse:
    """Building-owner invite with name, email, and role."""
    if actor.is_super_admin or "users.create" not in actor.permissions or not actor.client_id:
        raise HTTPException(status_code=403, detail="Forbidden.")
    try:
        record, _result = service.create_building(
            name=body.name,
            email=body.email,
            role_key=body.role_key,
            client_id=actor.client_id,
            invited_by_user_id=actor.user_id,
        )
    except DuplicateEmail as error:
        raise HTTPException(status_code=409, detail="Email already registered.") from error
    except InvitationEmailFailed as error:
        raise HTTPException(status_code=502, detail=error.message) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _response(record)


@router.post("/{invitation_id}/resend", response_model=InvitationResponse)
def resend_invitation(
    invitation_id: str,
    actor: Actor = Depends(get_current_actor),
    service: InvitationService = Depends(_service),
) -> InvitationResponse:
    """Resend an invitation email and rotate its token."""
    if not actor.is_super_admin and "users.create" not in actor.permissions:
        raise HTTPException(status_code=403, detail="Forbidden.")
    try:
        record, _result = service.resend(
            invitation_id,
            is_super_admin=actor.is_super_admin,
            client_id=actor.client_id,
            actor_user_id=actor.user_id,
        )
    except InvitationNotFound as error:
        raise HTTPException(status_code=404, detail="Invitation not found.") from error
    except InvitationForbidden as error:
        raise HTTPException(status_code=403, detail="Forbidden.") from error
    except InvitationAlreadyUsed as error:
        raise HTTPException(status_code=409, detail="Invitation already registered.") from error
    except InvitationEmailFailed as error:
        raise HTTPException(status_code=502, detail=error.message) from error
    return _response(record)


@router.delete("/{invitation_id}", status_code=204)
def delete_invitation(
    invitation_id: str,
    actor: Actor = Depends(get_current_actor),
    service: InvitationService = Depends(_service),
) -> None:
    """Delete an invitation row."""
    if not actor.is_super_admin and "users.create" not in actor.permissions:
        raise HTTPException(status_code=403, detail="Forbidden.")
    try:
        service.delete(
            invitation_id,
            is_super_admin=actor.is_super_admin,
            client_id=actor.client_id,
        )
    except InvitationNotFound as error:
        raise HTTPException(status_code=404, detail="Invitation not found.") from error
    except InvitationForbidden as error:
        raise HTTPException(status_code=403, detail="Forbidden.") from error


@router.get("/by-token/{token}", response_model=PublicInvitationResponse)
def get_invitation_by_token(
    token: str,
    service: InvitationService = Depends(_service),
) -> PublicInvitationResponse:
    """Public preview for the register form."""
    try:
        record = service.get_public(token)
    except InvitationNotFound as error:
        raise HTTPException(status_code=404, detail="Invitation not found.") from error
    return PublicInvitationResponse(
        kind=record.kind,
        name=record.name,
        email=record.email,
        building_name=record.building_name,
        role_key=record.role_key,
        status=record.status,
    )


@router.post("/by-token/{token}/accept-platform", response_model=PublicInvitationResponse)
def accept_platform_invitation(
    token: str,
    body: AcceptPlatformInvitationRequest,
    service: InvitationService = Depends(_service),
) -> PublicInvitationResponse:
    """Complete a platform invitation (new building client)."""
    try:
        record = service.accept_platform(
            token,
            building_name=body.building_name,
            address=body.address,
            password=body.password,
        )
    except InvitationNotFound as error:
        raise HTTPException(status_code=404, detail="Invitation not found.") from error
    except InvitationAlreadyUsed as error:
        raise HTTPException(status_code=409, detail="Invitation already registered.") from error
    except DuplicateEmail as error:
        raise HTTPException(status_code=409, detail="Email already registered.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return PublicInvitationResponse(
        kind=record.kind,
        name=record.name,
        email=record.email,
        building_name=record.building_name,
        role_key=record.role_key,
        status=record.status,
    )


@router.post("/by-token/{token}/accept-building", response_model=PublicInvitationResponse)
def accept_building_invitation(
    token: str,
    body: AcceptBuildingInvitationRequest,
    service: InvitationService = Depends(_service),
) -> PublicInvitationResponse:
    """Complete a building invitation (join with assigned role)."""
    try:
        record = service.accept_building(
            token,
            password=body.password,
            floor_number=body.floor_number,
            apartment_number=body.apartment_number,
        )
    except InvitationNotFound as error:
        raise HTTPException(status_code=404, detail="Invitation not found.") from error
    except InvitationAlreadyUsed as error:
        raise HTTPException(status_code=409, detail="Invitation already registered.") from error
    except DuplicateEmail as error:
        raise HTTPException(status_code=409, detail="Email already registered.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return PublicInvitationResponse(
        kind=record.kind,
        name=record.name,
        email=record.email,
        building_name=record.building_name,
        role_key=record.role_key,
        status=record.status,
    )


@router.get("/track/{token}")
def track_invitation_open(
    token: str,
    service: InvitationService = Depends(_service),
) -> Response:
    """Email open tracker (1x1 GIF). Always returns the pixel."""
    cleaned = token.removesuffix(".gif")
    service.mark_opened(cleaned)
    return Response(
        content=tracking_pixel_bytes(),
        media_type="image/gif",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )
