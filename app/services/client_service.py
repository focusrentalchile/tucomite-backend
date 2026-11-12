"""Use cases for platform clients and their first admin user."""

import secrets
import uuid
from dataclasses import replace
from datetime import date, timedelta

from app.domain.access import (
    ClientRecord,
    DuplicateEmail,
    UnknownRole,
    UserRecord,
)
from app.repositories.access_repository import AccessRepository
from app.repositories.client_repository import ClientRepository
from app.utils.passwords import hash_password

LICENSE_RENEWAL_DAYS = 30


class DuplicateClientName(Exception):
    """Raised when a client name is already taken."""


class ClientNotFound(Exception):
    """Raised when a client id does not exist."""


class LicenseStillActive(Exception):
    """Raised when renewing a client whose license has not ended yet."""

    def __init__(self, days_remaining: int) -> None:
        self.days_remaining = days_remaining
        super().__init__(f"License still has {days_remaining} day(s) remaining.")


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
        address: str = "",
        responsible_name: str = "",
        *,
        must_change_password: bool = False,
        require_activation: bool = False,
    ) -> tuple[ClientRecord, UserRecord]:
        """Create a client owner and a default building administrator for that license."""
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Client name is required.")
        starts, ends = self._validated_license(license_starts_at, license_ends_at)
        if self._clients.get_client_by_name(cleaned_name) is not None:
            raise DuplicateClientName(cleaned_name)

        normalized = email.strip().lower()
        if self._access.get_user_by_email(normalized) is not None:
            raise DuplicateEmail(normalized)

        from app.core.access_catalog import access_catalog
        from app.services.access_bootstrap import _ensure_starter_roles

        _ensure_starter_roles(self._access, access_catalog.permission_keys())
        owner_role = next(
            (role for role in self._access.list_roles() if role.name.casefold() == "client"),
            None,
        )
        if owner_role is None:
            raise UnknownRole("client")

        client_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        password_hash = hash_password(password)
        cleaned_responsible = responsible_name.strip()
        activation_token = secrets.token_urlsafe(32) if require_activation else None
        user = UserRecord(
            id=user_id,
            full_name=cleaned_responsible or cleaned_name,
            email=normalized,
            password_hash=password_hash,
            role_id=owner_role.id,
            client_id=client_id,
            must_change_password=must_change_password,
            activation_token=activation_token,
        )
        self._access.add_user(user)
        client = ClientRecord(
            id=client_id,
            name=cleaned_name,
            admin_user_id=user_id,
            address=address.strip(),
            responsible_name=cleaned_responsible,
            license_starts_at=starts,
            license_ends_at=ends,
        )
        self._clients.add_client(client)
        self.ensure_default_administrator(
            client_id=client_id,
            owner_email=normalized,
            password_hash=password_hash,
            building_name=cleaned_name,
        )
        return client, user

    def ensure_default_administrator(
        self,
        *,
        client_id: str,
        owner_email: str,
        password_hash: str,
        building_name: str,
    ) -> UserRecord | None:
        """Ensure one administrator user for the building when a license is opened.

        The administrator keeps this building as home (`client_id`) and can later
        import other buildings into the same account via Gestión workspace links.
        """
        admin_role = next(
            (role for role in self._access.list_roles() if role.name.casefold() == "administrator"),
            None,
        )
        if admin_role is None:
            return None

        for existing in self._access.list_users():
            if existing.client_id == client_id and existing.role_id == admin_role.id:
                return existing

        admin_email = self._default_administrator_email(owner_email)
        if self._access.get_user_by_email(admin_email) is not None:
            suffix = client_id.replace("-", "")[:8]
            local, _, domain = admin_email.partition("@")
            admin_email = f"{local}.{suffix}@{domain}" if domain else f"{admin_email}.{suffix}"

        record = UserRecord(
            id=str(uuid.uuid4()),
            full_name=f"Administrador · {building_name}"[:120],
            email=admin_email,
            password_hash=password_hash,
            role_id=admin_role.id,
            client_id=client_id,
        )
        self._access.add_user(record)
        return record

    def update_client(
        self,
        client_id: str,
        name: str,
        email: str,
        password: str | None,
        license_starts_at: str,
        license_ends_at: str,
        address: str = "",
        responsible_name: str = "",
    ) -> tuple[ClientRecord, UserRecord]:
        """Update a client name, license, and building-owner credentials."""
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

        cleaned_responsible = responsible_name.strip()
        updated_admin = UserRecord(
            id=admin.id,
            full_name=cleaned_responsible or admin.full_name or cleaned_name,
            email=normalized,
            password_hash=hash_password(password) if password else admin.password_hash,
            role_id=admin.role_id,
            client_id=client_id,
            period_id=admin.period_id,
            floor_number=admin.floor_number,
            apartment_number=admin.apartment_number,
            account_closed_at=admin.account_closed_at,
            must_change_password=True if password else admin.must_change_password,
            activation_token=admin.activation_token,
        )
        self._access.save_user(updated_admin)
        updated = ClientRecord(
            id=client.id,
            name=cleaned_name,
            admin_user_id=admin.id,
            address=address.strip(),
            responsible_name=cleaned_responsible,
            license_starts_at=starts,
            license_ends_at=ends,
        )
        self._clients.save_client(updated)
        return updated, updated_admin

    def renew_license(
        self,
        client_id: str,
        *,
        today: date | None = None,
        days: int = LICENSE_RENEWAL_DAYS,
    ) -> tuple[ClientRecord, UserRecord]:
        """Extend a client license by ``days`` only when the current window has ended."""
        client = self.get_client(client_id)
        admin = self._access.get_user(client.admin_user_id)
        if admin is None:
            raise ClientNotFound(client_id)
        current = today or date.today()
        ends = None
        if client.license_ends_at:
            try:
                ends = date.fromisoformat(client.license_ends_at.strip()[:10])
            except ValueError as error:
                raise ValueError("License end date must use YYYY-MM-DD.") from error
        if ends is not None and current <= ends:
            raise LicenseStillActive((ends - current).days)
        starts = current
        new_ends = current + timedelta(days=days)
        updated = ClientRecord(
            id=client.id,
            name=client.name,
            admin_user_id=client.admin_user_id,
            address=client.address,
            responsible_name=client.responsible_name,
            license_starts_at=starts.isoformat(),
            license_ends_at=new_ends.isoformat(),
        )
        self._clients.save_client(updated)
        return updated, admin

    def delete_client(self, client_id: str) -> None:
        """Delete a client and every user belonging to that client."""
        self.get_client(client_id)
        for user in self._access.list_users():
            if user.client_id != client_id:
                continue
            if user.period_id:
                self._access.save_user(replace(user, period_id=None))
        session = getattr(self._clients, "_session", None)
        if session is not None:
            from app.repositories.client_purge import purge_client_dependencies

            purge_client_dependencies(session, client_id)
        for user in self._access.list_users():
            if user.client_id == client_id:
                self._access.delete_user(user.id)
        self._clients.delete_client(client_id)

    def _default_administrator_email(self, owner_email: str) -> str:
        local, sep, domain = owner_email.partition("@")
        if not sep or not domain:
            return f"administrador.{owner_email}@tucomite.local"
        return f"administrador.{local}@{domain}"

    def _validated_license(self, starts_at: str, ends_at: str) -> tuple[str, str]:
        try:
            start = date.fromisoformat(starts_at.strip()[:10])
            end = date.fromisoformat(ends_at.strip()[:10])
        except ValueError as error:
            raise ValueError("License dates must use YYYY-MM-DD.") from error
        if end < start:
            raise ValueError("License end date must be on or after the start date.")
        return start.isoformat(), end.isoformat()
