"""MySQL repository for platform clients."""

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.access import ClientRecord
from app.models.access import ClientModel


class ClientRepository(Protocol):
    """Persistence port for clients."""

    def list_clients(self) -> list[ClientRecord]:
        """Return every client ordered by name."""

    def get_client(self, client_id: str) -> ClientRecord | None:
        """Return one client, or None."""

    def get_client_by_name(self, name: str) -> ClientRecord | None:
        """Return a client with this name, or None."""

    def add_client(self, client: ClientRecord) -> None:
        """Insert a client."""


class SqlClientRepository:
    """SQLAlchemy adapter for the clients table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_clients(self) -> list[ClientRecord]:
        rows = self._session.scalars(select(ClientModel).order_by(ClientModel.name)).all()
        return [self._client(row) for row in rows]

    def get_client(self, client_id: str) -> ClientRecord | None:
        row = self._session.get(ClientModel, client_id)
        if row is None:
            return None
        return self._client(row)

    def get_client_by_name(self, name: str) -> ClientRecord | None:
        row = self._session.scalar(select(ClientModel).where(ClientModel.name == name))
        if row is None:
            return None
        return self._client(row)

    def add_client(self, client: ClientRecord) -> None:
        self._session.add(
            ClientModel(id=client.id, name=client.name, admin_user_id=client.admin_user_id),
        )
        self._session.flush()

    def _client(self, row: ClientModel) -> ClientRecord:
        return ClientRecord(id=row.id, name=row.name, admin_user_id=row.admin_user_id)
