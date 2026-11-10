"""Use cases for the building wall and sales feed."""

from datetime import datetime, timezone
from uuid import uuid4

from app.domain.building_wall import (
    WALL_KINDS,
    BuildingWallPostNotFound,
    BuildingWallPostRecord,
    InvalidBuildingWallKind,
)
from app.repositories.building_wall_repository import BuildingWallRepository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BuildingWallService:
    """Public posts shared with everyone in the same building."""

    def __init__(self, repository: BuildingWallRepository) -> None:
        self._repository = repository

    def list_posts(self, client_id: str, kind: str | None = None) -> list[BuildingWallPostRecord]:
        """List wall or sales posts for one building."""
        if kind is not None and kind not in WALL_KINDS:
            raise InvalidBuildingWallKind()
        return self._repository.list_for_client(client_id, kind)

    def create_post(
        self,
        *,
        client_id: str,
        author_user_id: str,
        author_name: str,
        kind: str,
        body: str,
        title: str | None = None,
        price: str | None = None,
        image_name: str | None = None,
        image_url: str | None = None,
    ) -> BuildingWallPostRecord:
        """Create a wall comment/photo or a sales listing."""
        cleaned_kind = kind.strip().lower()
        if cleaned_kind not in WALL_KINDS:
            raise InvalidBuildingWallKind()
        cleaned_body = body.strip()
        cleaned_title = (title or "").strip() or None
        cleaned_price = (price or "").strip() or None
        cleaned_image_name = (image_name or "").strip() or None
        cleaned_image_url = (image_url or "").strip() or None
        if cleaned_image_url and not cleaned_image_name:
            cleaned_image_name = "foto.jpg"
        if not cleaned_body and not cleaned_image_url:
            raise ValueError("Post body or image is required.")
        if not cleaned_body:
            cleaned_body = ""
        if cleaned_kind == "sale" and not cleaned_title:
            raise ValueError("Sale title is required.")
        record = BuildingWallPostRecord(
            id=str(uuid4()),
            client_id=client_id,
            author_user_id=author_user_id,
            author_name=author_name,
            kind=cleaned_kind,
            body=cleaned_body,
            title=cleaned_title,
            price=cleaned_price,
            image_name=cleaned_image_name,
            image_url=cleaned_image_url,
            created_at=_now(),
        )
        self._repository.add(record)
        created = self._repository.get(record.id)
        if created is None:
            return record
        return created

    def delete_post(
        self,
        post_id: str,
        *,
        actor_user_id: str,
        is_super_admin: bool,
        client_id: str,
    ) -> None:
        """Delete a post owned by the actor in the same building."""
        post = self._repository.get(post_id)
        if post is None:
            raise BuildingWallPostNotFound()
        if post.client_id != client_id and not is_super_admin:
            raise PermissionError("Forbidden.")
        if not is_super_admin and post.author_user_id != actor_user_id:
            raise PermissionError("Forbidden.")
        self._repository.delete(post_id)
