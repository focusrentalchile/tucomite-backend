"""Unit tests for role permissions and user creation."""

import pytest

from app.core.access_catalog import AccessCatalog
from app.domain.access import (
    DuplicateEmail,
    DuplicateRoleName,
    ModuleDefinition,
    ProtectedRole,
    ProtectedUser,
    UnknownPermission,
    UnknownRole,
)
from app.services.access_bootstrap import STARTER_ROLES, bootstrap_access
from app.services.access_service import PermissionPolicy, RoleService, UserService
from tests.support.memory_access_repository import InMemoryAccessRepository


def catalog() -> AccessCatalog:
    registered = AccessCatalog()
    registered.register(ModuleDefinition(key="users", functionalities=("view", "create")))
    registered.register(ModuleDefinition(key="roles", functionalities=("view", "update")))
    return registered


def test_bootstrap_grants_every_catalog_permission_to_the_system_role() -> None:
    repository = InMemoryAccessRepository()
    registered = catalog()

    bootstrap_access(repository, registered)

    role = repository.get_system_role()
    assert role is not None
    assert role.permissions == registered.permission_keys()
    assert repository.list_modules()[0].key == "users"


def test_bootstrap_creates_the_building_groups_once() -> None:
    repository = InMemoryAccessRepository()
    registered = catalog()
    registered.register(ModuleDefinition(key="agreements", functionalities=("view", "vote")))
    registered.register(ModuleDefinition(key="matters", functionalities=("create", "comment")))
    registered.register(ModuleDefinition(key="tasks", functionalities=("assign",)))
    registered.register(ModuleDefinition(key="progress", functionalities=("view", "update")))
    registered.register(ModuleDefinition(key="documents", functionalities=("view",)))
    registered.register(ModuleDefinition(key="notifications", functionalities=("receive",)))

    bootstrap_access(repository, registered)
    bootstrap_access(repository, registered)

    roles = {role.name: role for role in repository.list_roles()}
    assert roles["committee"].permissions == STARTER_ROLES["committee"]
    assert "agreements.vote" not in roles["administrator"].permissions
    assert roles["resident"].permissions == frozenset(
        {"agreements.view", "progress.view", "documents.view", "notifications.receive"}
    )
    assert sum(1 for role in repository.list_roles() if role.name == "committee") == 1


def test_checkbox_grants_and_removes_one_permission() -> None:
    repository = InMemoryAccessRepository()
    registered = catalog()
    service = RoleService(repository, registered)
    role = service.create_role("committee")

    granted = service.set_permission(role.id, "users", "view", True)
    assert granted.permissions == frozenset({"users.view"})

    cleared = service.set_permission(role.id, "users", "view", False)
    assert cleared.permissions == frozenset()


def test_system_role_rejects_permission_changes() -> None:
    repository = InMemoryAccessRepository()
    registered = catalog()
    bootstrap_access(repository, registered)
    service = RoleService(repository, registered)
    role = repository.get_system_role()
    assert role is not None

    with pytest.raises(ProtectedRole):
        service.set_permission(role.id, "users", "view", False)


def test_unknown_permission_is_rejected() -> None:
    repository = InMemoryAccessRepository()
    service = RoleService(repository, catalog())
    role = service.create_role("gatehouse")

    with pytest.raises(UnknownPermission):
        service.set_permission(role.id, "billing", "view", True)


def test_duplicate_role_name_is_rejected() -> None:
    service = RoleService(InMemoryAccessRepository(), catalog())
    service.create_role("committee")

    with pytest.raises(DuplicateRoleName):
        service.create_role(" committee ")


def test_policy_matches_a_single_permission_key() -> None:
    policy = PermissionPolicy()

    assert policy.allows(frozenset({"users.view"}), "users", "view") is True
    assert policy.allows(frozenset({"users.view"}), "users", "create") is False


def test_create_user_assigns_a_role_and_rejects_a_duplicate_email() -> None:
    repository = InMemoryAccessRepository()
    registered = catalog()
    bootstrap_access(repository, registered)
    role = RoleService(repository, registered).create_role("committee")
    users = UserService(repository)

    created = users.create_user("Ana Pérez", "Ana@Example.com", "secreto-1", role.id)

    assert created.email == "ana@example.com"
    assert created.password_hash != "secreto-1"
    assert created.role_id == role.id
    with pytest.raises(DuplicateEmail):
        users.create_user("Ana", "ana@example.com", "secreto-2", role.id)
    with pytest.raises(UnknownRole):
        users.create_user("Luis", "luis@example.com", "secreto-2", "missing")


def test_update_and_delete_user() -> None:
    repository = InMemoryAccessRepository()
    registered = catalog()
    bootstrap_access(repository, registered)
    role = RoleService(repository, registered).create_role("porters")
    users = UserService(repository)
    created = users.create_user("Ana Pérez", "ana@example.com", "secreto-1", role.id)

    updated = users.update_user(created.id, "Ana María", "ana@example.com", None)
    assert updated.full_name == "Ana María"
    assert updated.password_hash == created.password_hash

    users.delete_user(created.id)
    assert all(user.id != created.id for user in users.list_users())

    admin = next(user for user in users.list_users() if user.email == "admin@tucomite.local")
    with pytest.raises(ProtectedUser):
        users.delete_user(admin.id)
