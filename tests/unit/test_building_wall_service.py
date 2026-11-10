"""Unit tests for building wall and sales posts."""

import pytest

from app.domain.building_wall import BuildingWallPostRecord, InvalidBuildingWallKind
from app.services.building_wall_service import BuildingWallService


class MemoryBuildingWallRepository:
    def __init__(self) -> None:
        self.posts: dict[str, BuildingWallPostRecord] = {}

    def list_for_client(self, client_id: str, kind: str | None = None) -> list[BuildingWallPostRecord]:
        items = [item for item in self.posts.values() if item.client_id == client_id]
        if kind:
            items = [item for item in items if item.kind == kind]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def get(self, post_id: str) -> BuildingWallPostRecord | None:
        return self.posts.get(post_id)

    def add(self, record: BuildingWallPostRecord) -> None:
        self.posts[record.id] = record

    def delete(self, post_id: str) -> bool:
        return self.posts.pop(post_id, None) is not None


def test_create_wall_post_with_photo_only() -> None:
    service = BuildingWallService(MemoryBuildingWallRepository())
    created = service.create_post(
        client_id="c1",
        author_user_id="u1",
        author_name="Ana",
        kind="wall",
        body="",
        image_name="foto.png",
        image_url="data:image/png;base64,abc",
    )
    assert created.kind == "wall"
    assert created.image_url.startswith("data:image")


def test_sale_requires_title() -> None:
    service = BuildingWallService(MemoryBuildingWallRepository())
    with pytest.raises(ValueError, match="Sale title"):
        service.create_post(
            client_id="c1",
            author_user_id="u1",
            author_name="Ana",
            kind="sale",
            body="Silla usada",
        )


def test_rejects_invalid_kind() -> None:
    service = BuildingWallService(MemoryBuildingWallRepository())
    with pytest.raises(InvalidBuildingWallKind):
        service.create_post(
            client_id="c1",
            author_user_id="u1",
            author_name="Ana",
            kind="story",
            body="Hola",
        )


def test_owner_can_delete_post() -> None:
    repo = MemoryBuildingWallRepository()
    service = BuildingWallService(repo)
    created = service.create_post(
        client_id="c1",
        author_user_id="u1",
        author_name="Ana",
        kind="wall",
        body="Hola edificio",
    )
    service.delete_post(
        created.id,
        actor_user_id="u1",
        is_super_admin=False,
        client_id="c1",
    )
    assert repo.get(created.id) is None
