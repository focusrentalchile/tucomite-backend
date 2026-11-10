"""Persistence for building wall and sales posts."""

from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.building_wall import BuildingWallPostRecord
from app.models.access import UserModel
from app.models.building_wall import BuildingWallPostModel


def _iso(value: datetime | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.isoformat()


class BuildingWallRepository(Protocol):
    """Port used by BuildingWallService."""

    def list_for_client(self, client_id: str, kind: str | None = None) -> list[BuildingWallPostRecord]: ...

    def get(self, post_id: str) -> BuildingWallPostRecord | None: ...

    def add(self, record: BuildingWallPostRecord) -> None: ...

    def delete(self, post_id: str) -> bool: ...


class SqlBuildingWallRepository:
    """SQLAlchemy adapter for building wall posts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_client(self, client_id: str, kind: str | None = None) -> list[BuildingWallPostRecord]:
        stmt = select(BuildingWallPostModel).where(BuildingWallPostModel.client_id == client_id)
        if kind:
            stmt = stmt.where(BuildingWallPostModel.kind == kind)
        rows = self._session.scalars(stmt.order_by(BuildingWallPostModel.created_at.desc())).all()
        return [self._post(row) for row in rows]

    def get(self, post_id: str) -> BuildingWallPostRecord | None:
        row = self._session.get(BuildingWallPostModel, post_id)
        if row is None:
            return None
        return self._post(row)

    def add(self, record: BuildingWallPostRecord) -> None:
        self._session.add(
            BuildingWallPostModel(
                id=record.id or str(uuid4()),
                client_id=record.client_id,
                author_user_id=record.author_user_id,
                kind=record.kind,
                body=record.body,
                title=record.title,
                price=record.price,
                image_name=record.image_name,
                image_url=record.image_url,
            ),
        )
        self._session.flush()

    def delete(self, post_id: str) -> bool:
        row = self._session.get(BuildingWallPostModel, post_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True

    def _post(self, row: BuildingWallPostModel) -> BuildingWallPostRecord:
        author_name = ""
        user = self._session.get(UserModel, row.author_user_id)
        if user is not None:
            author_name = user.full_name or user.email or ""
        return BuildingWallPostRecord(
            id=row.id,
            client_id=row.client_id,
            author_user_id=row.author_user_id,
            author_name=author_name,
            kind=row.kind,
            body=row.body,
            title=row.title,
            price=row.price,
            image_name=row.image_name,
            image_url=row.image_url,
            created_at=_iso(row.created_at),
        )
