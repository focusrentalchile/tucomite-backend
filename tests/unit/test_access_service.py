"""Unit tests for role permissions and user creation."""

import pytest

from app.core.access_catalog import AccessCatalog
from app.domain.access import (
    ClientRecord,
    DuplicateEmail,
    DuplicateRoleName,
    ModuleDefinition,
    ProtectedRole,
    ProtectedUser,
    UnknownPermission,
    UnknownRole,
    UserRecord,
)
from app.services.access_bootstrap import DEMO_CLIENT_NAME, STARTER_ROLES, bootstrap_access
from app.services.access_service import PermissionPolicy, RoleService, UserService
from app.utils.passwords import hash_password
from tests.support.memory_access_repository import InMemoryAccessRepository


class _MemoryClients:
    """Minimal client store for bootstrap unit tests."""

    def __init__(self, clients: list[ClientRecord] | None = None) -> None:
        self._clients = list(clients or [])

    def list_clients(self) -> list[ClientRecord]:
        return list(self._clients)

    def get_client(self, client_id: str) -> ClientRecord | None:
        return next((item for item in self._clients if item.id == client_id), None)

    def get_client_by_name(self, name: str) -> ClientRecord | None:
        return next((item for item in self._clients if item.name == name), None)

    def add_client(self, client: ClientRecord) -> None:
        self._clients.append(client)

    def save_client(self, client: ClientRecord) -> None:
        self._clients = [client if item.id == client.id else item for item in self._clients]

    def delete_client(self, client_id: str) -> None:
        self._clients = [item for item in self._clients if item.id != client_id]


def catalog() -> AccessCatalog:
    registered = AccessCatalog()
    registered.register(ModuleDefinition(key="users", functionalities=("view", "create")))
    registered.register(ModuleDefinition(key="roles", functionalities=("view", "create", "update", "delete")))
    registered.register(ModuleDefinition(key="clients", functionalities=("view", "create")))
    registered.register(ModuleDefinition(key="agreements", functionalities=("view", "vote")))
    registered.register(ModuleDefinition(key="matters", functionalities=("create", "comment")))
    registered.register(ModuleDefinition(key="tasks", functionalities=("assign",)))
    registered.register(ModuleDefinition(key="progress", functionalities=("view", "update")))
    registered.register(ModuleDefinition(key="documents", functionalities=("view",)))
    registered.register(ModuleDefinition(key="notifications", functionalities=("receive",)))
    registered.register(
        ModuleDefinition(
            key="support",
            functionalities=("view", "create", "reply", "update", "approve_import"),
        ),
    )
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

    bootstrap_access(repository, registered)
    bootstrap_access(repository, registered)

    roles = {role.name: role for role in repository.list_roles()}
    assert roles["committee"].permissions == STARTER_ROLES["committee"]
    assert "users.view" not in roles["administrator"].permissions
    assert "agreements.view" in roles["administrator"].permissions
    assert "support.view" in roles["administrator"].permissions
    assert roles["resident"].permissions == STARTER_ROLES["resident"]
    assert "client" in roles
    assert sum(1 for role in repository.list_roles() if role.name == "committee") == 1


def test_bootstrap_seeds_demo_users_for_each_building_role() -> None:
    repository = InMemoryAccessRepository()
    registered = catalog()
    bootstrap_access(repository, registered)
    owner = next(role for role in repository.list_roles() if role.name == "client")
    repository.add_user(
        UserRecord(
            id="owner-1",
            full_name="Cliente demo",
            email="client@tucomite.cl",
            password_hash=hash_password("123456"),
            role_id=owner.id,
            client_id="client-demo",
        ),
    )
    clients = _MemoryClients(
        [
            ClientRecord(
                id="client-demo",
                name=DEMO_CLIENT_NAME,
                admin_user_id="owner-1",
                license_starts_at="2026-01-01",
                license_ends_at="2027-01-01",
            ),
        ],
    )

    bootstrap_access(repository, registered, clients)
    bootstrap_access(repository, registered, clients)

    by_email = {user.email: user for user in repository.list_users()}
    roles = {role.id: role.name for role in repository.list_roles()}
    assert roles[by_email["administrador@demo.tucomite.local"].role_id] == "administrator"
    assert roles[by_email["comite@demo.tucomite.local"].role_id] == "committee"
    assert roles[by_email["residente@demo.tucomite.local"].role_id] == "resident"
    assert by_email["administrador@demo.tucomite.local"].client_id == "client-demo"
    assert sum(1 for user in repository.list_users() if user.email.endswith("@demo.tucomite.local")) == 3


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


def test_list_roles_hides_system_and_delete_removes_users() -> None:
    repository = InMemoryAccessRepository()
    registered = catalog()
    bootstrap_access(repository, registered)
    service = RoleService(repository, registered)
    users = UserService(repository)

    listed = service.list_roles()
    assert all(not role.system for role in listed)
    assert "administrator" in {role.name for role in listed}
    assert "committee" in {role.name for role in listed}
    assert "client" in {role.name for role in listed}
    assert "resident" in {role.name for role in listed}

    starter = next(role for role in listed if role.name == "committee")
    users.create_user("Ana Pérez", "ana@example.com", "secreto-1", starter.id)
    users.create_user("Luis Soto", "luis@example.com", "secreto-1", starter.id)
    assert repository.count_users_with_role(starter.id) == 2

    service.delete_role(starter.id)
    assert repository.get_role(starter.id) is None
    assert repository.count_users_with_role(starter.id) == 0
    assert repository.get_user_by_email("ana@example.com") is None
    assert repository.get_user_by_email("luis@example.com") is None

    system = repository.get_system_role()
    assert system is not None
    with pytest.raises(ProtectedRole):
        service.delete_role(system.id)


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
    role = next(item for item in repository.list_roles() if item.name == "committee")
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

    other = RoleService(repository, registered).create_role("guards")
    updated = users.update_user(created.id, "Ana María", "ana@example.com", None, other.id)
    assert updated.full_name == "Ana María"
    assert updated.password_hash == created.password_hash
    assert updated.role_id == other.id

    users.delete_user(created.id)
    assert all(user.id != created.id for user in users.list_users())

    system_role = repository.get_system_role()
    assert system_role is not None
    repository.add_user(
        UserRecord(
            id="system-user-1",
            full_name="Super admin",
            email="system@example.com",
            password_hash=hash_password("secret"),
            role_id=system_role.id,
            client_id=None,
        ),
    )
    with pytest.raises(ProtectedUser):
        users.delete_user("system-user-1")
