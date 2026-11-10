"""Building wall and sales feed endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_current_actor, get_db
from app.domain.building_wall import BuildingWallPostNotFound, InvalidBuildingWallKind
from app.models.access import UserModel
from app.repositories.building_wall_repository import SqlBuildingWallRepository
from app.schemas.building_wall import (
    BuildingWallPostListResponse,
    BuildingWallPostResponse,
    CreateBuildingWallPostRequest,
)
from app.services.building_wall_service import BuildingWallService

router = APIRouter(prefix="/building-wall", tags=["building-wall"])


def get_building_wall_service(db: Session = Depends(get_db)) -> BuildingWallService:
    """Build a wall service bound to the request session."""
    return BuildingWallService(SqlBuildingWallRepository(db))


def _actor_display_name(db: Session, user_id: str) -> str:
    user = db.get(UserModel, user_id)
    if user is None:
        return ""
    return user.full_name or user.email or ""


def _post_response(post) -> BuildingWallPostResponse:
    return BuildingWallPostResponse(
        id=post.id,
        client_id=post.client_id,
        author_user_id=post.author_user_id,
        author_name=post.author_name,
        kind=post.kind,
        body=post.body,
        title=post.title,
        price=post.price,
        image_name=post.image_name,
        image_url=post.image_url,
        created_at=post.created_at,
    )


@router.get("/posts", response_model=BuildingWallPostListResponse)
def list_building_wall_posts(
    kind: str | None = Query(default=None),
    actor: Actor = Depends(get_current_actor),
    service: BuildingWallService = Depends(get_building_wall_service),
) -> BuildingWallPostListResponse:
    """List public wall or sales posts for the actor's building."""
    if not actor.client_id:
        raise HTTPException(status_code=403, detail="Forbidden.")
    try:
        items = service.list_posts(actor.client_id, kind)
    except InvalidBuildingWallKind as error:
        raise HTTPException(status_code=422, detail="Invalid post kind.") from error
    return BuildingWallPostListResponse(items=[_post_response(item) for item in items])


@router.post("/posts", response_model=BuildingWallPostResponse, status_code=201)
def create_building_wall_post(
    body: CreateBuildingWallPostRequest,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
    service: BuildingWallService = Depends(get_building_wall_service),
) -> BuildingWallPostResponse:
    """Create a wall comment/photo or a sales listing for the actor's building."""
    if not actor.client_id:
        raise HTTPException(status_code=403, detail="Forbidden.")
    try:
        created = service.create_post(
            client_id=actor.client_id,
            author_user_id=actor.user_id,
            author_name=_actor_display_name(db, actor.user_id),
            kind=body.kind,
            body=body.body,
            title=body.title,
            price=body.price,
            image_name=body.image_name,
            image_url=body.image_url,
        )
    except InvalidBuildingWallKind as error:
        raise HTTPException(status_code=422, detail="Invalid post kind.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _post_response(created)


@router.delete("/posts/{post_id}", status_code=204)
def delete_building_wall_post(
    post_id: str,
    actor: Actor = Depends(get_current_actor),
    service: BuildingWallService = Depends(get_building_wall_service),
) -> None:
    """Delete an owned wall or sales post."""
    if not actor.client_id and not actor.is_super_admin:
        raise HTTPException(status_code=403, detail="Forbidden.")
    try:
        service.delete_post(
            post_id,
            actor_user_id=actor.user_id,
            is_super_admin=actor.is_super_admin,
            client_id=actor.client_id or "",
        )
    except BuildingWallPostNotFound as error:
        raise HTTPException(status_code=404, detail="Post not found.") from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail="Forbidden.") from error
