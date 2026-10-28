"""Use cases for platform clients and their first admin user."""

import uuid

from app.domain.access import (
    ClientRecord,
    DuplicateEmail,
    UnknownRole,
    UserRecord,
)
from app.repositories.access_repository import AccessRepository
from app.repositories.client_repository import ClientRepository
from app.utils.passwords import hash_password


class DuplicateClientName(Exception):
    """Raised when a client name is already taken."""


class ClientService:
    """Creates a client and its building administrator in one step."""

    def __init__(self, clients: ClientRepository, access: AccessRepository) -> None:
        self._clients = clients
        self._access = access

    def list_clients(self) -> list[ClientRecord]:
        """Return every client."""
        return self._clients.list_clients()

    def create_client(self, name: str, email: str, password: str) -> tuple[ClientRecord, UserRecord]:
        """Create a client and an administrator user for that client."""
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Client name is required.")
        if self._clients.get_client_by_name(cleaned_name) is not None:
            raise DuplicateClientName(cleaned_name)

        normalized = email.strip().lower()
        if self._access.get_user_by_email(normalized) is not None:
            raise DuplicateEmail(normalized)

        admin_role = next(
            (role for role in self._access.list_roles() if role.name.casefold() == "administrator"),
            None,
        )
        if admin_role is None:
            raise UnknownRole("administrator")

        client_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        user = UserRecord(
            id=user_id,
            full_name=cleaned_name,
            email=normalized,
            password_hash=hash_password(password),
            role_id=admin_role.id,
            client_id=client_id,
        )
        self._access.add_user(user)
        client = ClientRecord(id=client_id, name=cleaned_name, admin_user_id=user_id)
        self._clients.add_client(client)
        return client, user
