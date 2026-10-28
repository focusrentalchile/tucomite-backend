"""Use cases for platform clients and their first admin user."""

import uuid
from datetime import date

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


class ClientNotFound(Exception):
    """Raised when a client id does not exist."""


class ClientService:
    """Creates, updates, and deletes clients with their building users."""

    def __init__(self, clients: ClientRepository, access: AccessRepository) -> None:
        self._clients = clients
        self._access = access

    def list_clients(self) -> list[ClientRecord]:
        """Return every client."""
        return self._clients.list_clients()

    def get_client(self, client_id: str) -> ClientRecord:
        """Return one client or raise."""
        client = self._clients.get_client(client_id)
        if client is None:
            raise ClientNotFound(client_id)
        return client

    def create_client(
        self,
        name: str,
        email: str,
        password: str,
        license_starts_at: str,
        license_ends_at: str,
    ) -> tuple[ClientRecord, UserRecord]:
        """Create a client and an administrator user for that client."""
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Client name is required.")
        starts, ends = self._validated_license(license_starts_at, license_ends_at)
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
        client = ClientRecord(
            id=client_id,
            name=cleaned_name,
            admin_user_id=user_id,
            license_starts_at=starts,
            license_ends_at=ends,
        )
        self._clients.add_client(client)
        return client, user

    def update_client(
        self,
        client_id: str,
        name: str,
        email: str,
        password: str | None,
        license_starts_at: str,
        license_ends_at: str,
    ) -> tuple[ClientRecord, UserRecord]:
        """Update a client name, license, and administrator credentials."""
        client = self.get_client(client_id)
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Client name is required.")
        starts, ends = self._validated_license(license_starts_at, license_ends_at)
        existing = self._clients.get_client_by_name(cleaned_name)
        if existing is not None and existing.id != client_id:
            raise DuplicateClientName(cleaned_name)

        admin = self._access.get_user(client.admin_user_id)
        if admin is None:
            raise ClientNotFound(client_id)

        normalized = email.strip().lower()
        other = self._access.get_user_by_email(normalized)
        if other is not None and other.id != admin.id:
            raise DuplicateEmail(normalized)

        updated_admin = UserRecord(
            id=admin.id,
            full_name=admin.full_name or cleaned_name,
            email=normalized,
            password_hash=hash_password(password) if password else admin.password_hash,
            role_id=admin.role_id,
            client_id=client_id,
        )
        self._access.save_user(updated_admin)
        updated = ClientRecord(
            id=client.id,
            name=cleaned_name,
            admin_user_id=admin.id,
            license_starts_at=starts,
            license_ends_at=ends,
        )
        self._clients.save_client(updated)
        return updated, updated_admin

    def delete_client(self, client_id: str) -> None:
        """Delete a client and every user belonging to that client."""
        self.get_client(client_id)
        for user in self._access.list_users():
            if user.client_id == client_id:
                self._access.delete_user(user.id)
        self._clients.delete_client(client_id)

    def _validated_license(self, starts_at: str, ends_at: str) -> tuple[str, str]:
        try:
            start = date.fromisoformat(starts_at.strip()[:10])
            end = date.fromisoformat(ends_at.strip()[:10])
        except ValueError as error:
            raise ValueError("License dates must use YYYY-MM-DD.") from error
        if end < start:
            raise ValueError("License end date must be on or after the start date.")
        return start.isoformat(), end.isoformat()
