"""Use cases for roles and users."""

import uuid

from app.core.access_catalog import AccessCatalog
from app.domain.access import (
    SUPER_ADMIN_EMAIL,
    DuplicateEmail,
    DuplicateRoleName,
    ProtectedRole,
    ProtectedUser,
    RoleNotFound,
    RoleRecord,
    UnknownPermission,
    UnknownRole,
    UserNotFound,
    UserRecord,
    permission_key,
)
from app.repositories.access_repository import AccessRepository
from app.utils.passwords import hash_password


class PermissionPolicy:
    """Decides whether a set of permission keys allows one action."""

    def allows(self, permissions: frozenset[str], module_key: str, functionality_key: str) -> bool:
        """Return True when the key is present."""
        return permission_key(module_key, functionality_key) in permissions


class RoleService:
    """Creates roles and grants or removes a single permission immediately."""

    def __init__(self, repository: AccessRepository, catalog: AccessCatalog) -> None:
        self._repository = repository
        self._catalog = catalog

    def list_catalog(self) -> list:
        """Return the modules stored for the permission matrix."""
        return self._repository.list_modules()

    def list_roles(self) -> list[RoleRecord]:
        """Return every role."""
        return self._repository.list_roles()

    def create_role(self, name: str) -> RoleRecord:
        """Create a role with no permissions yet."""
        cleaned = name.strip()
        if any(role.name.casefold() == cleaned.casefold() for role in self._repository.list_roles()):
            raise DuplicateRoleName(cleaned)
        role = RoleRecord(id=str(uuid.uuid4()), name=cleaned, system=False, permissions=frozenset())
        self._repository.add_role(role)
        return role

    def set_permission(
        self,
        role_id: str,
        module_key: str,
        functionality_key: str,
        granted: bool,
    ) -> RoleRecord:
        """Add or remove one permission. The system role stays fully granted."""
        role = self._repository.get_role(role_id)
        if role is None:
            raise RoleNotFound(role_id)
        if role.system:
            raise ProtectedRole(role_id)
        if not self._catalog.has(module_key, functionality_key):
            raise UnknownPermission(permission_key(module_key, functionality_key))
        permissions = set(role.permissions)
        key = permission_key(module_key, functionality_key)
        if granted:
            permissions.add(key)
        else:
            permissions.discard(key)
        updated = RoleRecord(id=role.id, name=role.name, system=False, permissions=frozenset(permissions))
        self._repository.save_role(updated)
        return updated


class UserService:
    """Creates people and assigns them a role."""

    def __init__(self, repository: AccessRepository) -> None:
        self._repository = repository

    def list_users(self) -> list[UserRecord]:
        """Return every user."""
        return self._repository.list_users()

    def create_user(
        self,
        full_name: str,
        email: str,
        password: str,
        role_id: str | None = None,
    ) -> UserRecord:
        """Create a user when the email is free and the role exists."""
        normalized = email.strip().lower()
        if self._repository.get_user_by_email(normalized) is not None:
            raise DuplicateEmail(normalized)
        assigned_role_id = role_id or self._default_role_id()
        if self._repository.get_role(assigned_role_id) is None:
            raise UnknownRole(assigned_role_id)
        user = UserRecord(
            id=str(uuid.uuid4()),
            full_name=full_name.strip(),
            email=normalized,
            password_hash=hash_password(password),
            role_id=assigned_role_id,
            client_id=None,
        )
        self._repository.add_user(user)
        return user

    def update_user(
        self,
        user_id: str,
        full_name: str,
        email: str,
        password: str | None = None,
    ) -> UserRecord:
        """Update name, email, and optionally the password."""
        current = self._repository.get_user(user_id)
        if current is None:
            raise UserNotFound()
        normalized = email.strip().lower()
        other = self._repository.get_user_by_email(normalized)
        if other is not None and other.id != user_id:
            raise DuplicateEmail(normalized)
        updated = UserRecord(
            id=current.id,
            full_name=full_name.strip(),
            email=normalized,
            password_hash=hash_password(password) if password else current.password_hash,
            role_id=current.role_id,
            client_id=current.client_id,
        )
        self._repository.save_user(updated)
        return updated

    def delete_user(self, user_id: str) -> None:
        """Delete a user that is not the seeded super admin."""
        current = self._repository.get_user(user_id)
        if current is None:
            raise UserNotFound()
        if current.email == SUPER_ADMIN_EMAIL:
            raise ProtectedUser()
        self._repository.delete_user(user_id)

    def _default_role_id(self) -> str:
        roles = self._repository.list_roles()
        preferred = next((role for role in roles if not role.system), None)
        if preferred is not None:
            return preferred.id
        if roles:
            return roles[0].id
        raise UnknownRole("")
