"""Keeps the MySQL access catalog and starter roles aligned with code."""

import uuid
from datetime import date, timedelta

from app.core.access_catalog import AccessCatalog
from app.domain.access import ClientRecord, RoleRecord, UserRecord
from app.repositories.access_repository import AccessRepository
from app.repositories.client_repository import ClientRepository
from app.utils.passwords import hash_password

DEMO_CLIENT_NAME = "Cliente de prueba"
# Shared by demo building accounts (administrator / committee / resident).
DEMO_BUILDING_PASSWORD = "123456"
# Building owner login. Legacy seed used admin@; bootstrap renames it.
DEMO_CLIENT_EMAIL = "client@tucomite.cl"
LEGACY_DEMO_CLIENT_EMAIL = "admin@tucomite.cl"

# English role keys. The admin site translates them in the Spanish locale.
STARTER_ROLES: dict[str, frozenset[str]] = {
    "committee": frozenset(
        {
            "agreements.view",
            "matters.create",
            "matters.comment",
            "agreements.vote",
            "tasks.assign",
            "progress.view",
            "progress.update",
            "documents.view",
            "notifications.receive",
        }
    ),
    "administrator": frozenset(
        {
            "agreements.view",
            "management.view",
            "management.create",
            "management.reply",
            "management.update",
            "notifications.receive",
        }
    ),
    "resident": frozenset(
        {
            "notifications.receive",
        }
    ),
    # Building owner. Full building tools except Gestión (administrators only).
    "client": frozenset(
        {
            "agreements.view",
            "agreements.vote",
            "matters.create",
            "matters.comment",
            "tasks.assign",
            "progress.view",
            "progress.update",
            "documents.view",
            "notifications.receive",
            "users.view",
            "users.create",
            "roles.view",
            "roles.create",
            "roles.update",
            "roles.delete",
        }
    ),
}

# No longer hidden from /roles for user assignment. The admin Roles screen may
# still filter starters separately for permission editing.
HIDDEN_ROLES: frozenset[str] = frozenset()


def bootstrap_access(
    repository: AccessRepository,
    catalog: AccessCatalog,
    clients: ClientRepository | None = None,
) -> None:
    """Sync modules and starter roles. Platform users are stored only in the database."""
    _migrate_legacy_management_permissions(repository)
    repository.replace_catalog(catalog.modules())
    keys = catalog.permission_keys()
    role = repository.get_system_role()
    if role is None:
        repository.add_role(
            RoleRecord(
                id=str(uuid.uuid4()),
                name="Super admin",
                system=True,
                permissions=keys,
            ),
        )
    elif role.permissions != keys:
        repository.save_role(RoleRecord(id=role.id, name=role.name, system=True, permissions=keys))
    _ensure_starter_roles(repository, keys)
    if clients is not None:
        _rename_legacy_client_email(repository)
        _ensure_building_owners_use_client_role(repository, clients)
        demo_client = clients.get_client_by_name(DEMO_CLIENT_NAME)
        if demo_client is not None:
            _ensure_demo_building_users(
                repository,
                demo_client.id,
                hash_password(DEMO_BUILDING_PASSWORD),
            )


def upsert_platform_accounts(
    repository: AccessRepository,
    clients: ClientRepository,
    *,
    super_admin_email: str,
    super_admin_password: str,
    demo_admin_email: str = DEMO_CLIENT_EMAIL,
    demo_admin_password: str,
    demo_client_name: str = DEMO_CLIENT_NAME,
    demo_admin_name: str = "Cliente demo",
) -> None:
    """Create or update platform accounts in MySQL. Credentials come from the caller, not source."""
    role = repository.get_system_role()
    if role is None:
        raise RuntimeError("System role is missing. Run bootstrap_access first.")
    owner_role = next(
        (item for item in repository.list_roles() if item.name.casefold() == "client"),
        None,
    )
    if owner_role is None:
        raise RuntimeError("Client role is missing. Run bootstrap_access first.")

    super_admin = _find_system_user(repository, role.id, super_admin_email)
    password_hash = hash_password(super_admin_password)
    if super_admin is None:
        repository.add_user(
            UserRecord(
                id=str(uuid.uuid4()),
                full_name="Super admin",
                email=super_admin_email,
                password_hash=password_hash,
                role_id=role.id,
                client_id=None,
            ),
        )
    else:
        repository.save_user(
            UserRecord(
                id=super_admin.id,
                full_name=super_admin.full_name or "Super admin",
                email=super_admin_email,
                password_hash=password_hash,
                role_id=role.id,
                client_id=None,
            ),
        )

    today = date.today()
    starts = today.isoformat()
    ends = (today + timedelta(days=365)).isoformat()
    client = clients.get_client_by_name(demo_client_name)
    demo_user = repository.get_user_by_email(demo_admin_email)
    if client is not None and demo_user is None:
        demo_user = repository.get_user(client.admin_user_id)
    demo_hash = hash_password(demo_admin_password)

    if client is None:
        client_id = str(uuid.uuid4())
        user_id = demo_user.id if demo_user is not None else str(uuid.uuid4())
        if demo_user is None:
            repository.add_user(
                UserRecord(
                    id=user_id,
                    full_name=demo_admin_name,
                    email=demo_admin_email,
                    password_hash=demo_hash,
                    role_id=owner_role.id,
                    client_id=client_id,
                ),
            )
        else:
            repository.save_user(
                UserRecord(
                    id=user_id,
                    full_name=demo_admin_name,
                    email=demo_admin_email,
                    password_hash=demo_hash,
                    role_id=owner_role.id,
                    client_id=client_id,
                ),
            )
        clients.add_client(
            ClientRecord(
                id=client_id,
                name=demo_client_name,
                admin_user_id=user_id,
                license_starts_at=starts,
                license_ends_at=ends,
            ),
        )
        _ensure_demo_building_users(repository, client_id, demo_hash)
        return

    user_id = demo_user.id if demo_user is not None else str(uuid.uuid4())
    if demo_user is None:
        repository.add_user(
            UserRecord(
                id=user_id,
                full_name=demo_admin_name,
                email=demo_admin_email,
                password_hash=demo_hash,
                role_id=owner_role.id,
                client_id=client.id,
            ),
        )
    else:
        repository.save_user(
            UserRecord(
                id=user_id,
                full_name=demo_admin_name,
                email=demo_admin_email,
                password_hash=demo_hash,
                role_id=owner_role.id,
                client_id=client.id,
            ),
        )
    clients.save_client(
        ClientRecord(
            id=client.id,
            name=client.name,
            admin_user_id=user_id,
            license_starts_at=client.license_starts_at or starts,
            license_ends_at=client.license_ends_at or ends,
        ),
    )
    _ensure_demo_building_users(repository, client.id, demo_hash)


def _ensure_demo_building_users(
    repository: AccessRepository,
    client_id: str,
    password_hash: str,
) -> None:
    """Ensure one demo user for administrator, committee, and resident."""
    by_name = {role.name.casefold(): role for role in repository.list_roles()}
    seeds = (
        ("administrator", "Administrador demo", "administrador@demo.tucomite.local"),
        ("committee", "Comité demo", "comite@demo.tucomite.local"),
        ("resident", "Residente demo", "residente@demo.tucomite.local"),
    )
    for role_name, full_name, email in seeds:
        role = by_name.get(role_name)
        if role is None:
            continue
        existing = repository.get_user_by_email(email)
        if existing is not None:
            if existing.client_id == client_id and existing.role_id == role.id:
                continue
            repository.save_user(
                UserRecord(
                    id=existing.id,
                    full_name=existing.full_name or full_name,
                    email=email,
                    password_hash=existing.password_hash or password_hash,
                    role_id=role.id,
                    client_id=client_id,
                ),
            )
            continue
        repository.add_user(
            UserRecord(
                id=str(uuid.uuid4()),
                full_name=full_name,
                email=email,
                password_hash=password_hash,
                role_id=role.id,
                client_id=client_id,
            ),
        )


def _rename_legacy_client_email(repository: AccessRepository) -> None:
    """Move the building owner from admin@ to client@ when the new address is free."""
    current = repository.get_user_by_email(DEMO_CLIENT_EMAIL)
    if current is not None:
        return
    legacy = repository.get_user_by_email(LEGACY_DEMO_CLIENT_EMAIL)
    if legacy is None:
        return
    repository.save_user(
        UserRecord(
            id=legacy.id,
            full_name=legacy.full_name,
            email=DEMO_CLIENT_EMAIL,
            password_hash=legacy.password_hash,
            role_id=legacy.role_id,
            client_id=legacy.client_id,
            period_id=legacy.period_id,
        ),
    )


def _ensure_building_owners_use_client_role(
    repository: AccessRepository,
    clients: ClientRepository,
) -> None:
    """Keep each building's owner account on the hidden client role."""
    owner_role = next(
        (item for item in repository.list_roles() if item.name.casefold() == "client"),
        None,
    )
    if owner_role is None:
        return
    for client in clients.list_clients():
        user = repository.get_user(client.admin_user_id)
        if user is None or user.role_id == owner_role.id:
            continue
        repository.save_user(
            UserRecord(
                id=user.id,
                full_name=user.full_name,
                email=user.email,
                password_hash=user.password_hash,
                role_id=owner_role.id,
                client_id=user.client_id or client.id,
            ),
        )


def _migrate_legacy_management_permissions(repository: AccessRepository) -> None:
    """Rewrite legacy support.* / gestion.* grants to management.* before catalog sync."""

    def rewrite(permission: str) -> str:
        if permission.startswith("support."):
            return "management." + permission[len("support.") :]
        if permission.startswith("gestion."):
            return "management." + permission[len("gestion.") :]
        return permission

    for role in repository.list_roles():
        rewritten = frozenset(rewrite(permission) for permission in role.permissions)
        if rewritten == role.permissions:
            continue
        repository.save_role(
            RoleRecord(id=role.id, name=role.name, system=role.system, permissions=rewritten),
        )


def _ensure_starter_roles(repository: AccessRepository, keys: frozenset[str]) -> None:
    """Add or refresh each building group so catalog actions stay available."""
    by_name = {role.name.casefold(): role for role in repository.list_roles()}
    for name, permissions in STARTER_ROLES.items():
        allowed = frozenset(permission for permission in permissions if permission in keys)
        if not allowed:
            continue
        current = by_name.get(name.casefold())
        if current is None:
            repository.add_role(
                RoleRecord(id=str(uuid.uuid4()), name=name, system=False, permissions=allowed),
            )
            continue
        if current.system or current.permissions == allowed:
            continue
        repository.save_role(
            RoleRecord(id=current.id, name=current.name, system=False, permissions=allowed),
        )


def _find_system_user(repository: AccessRepository, role_id: str, email: str) -> UserRecord | None:
    user = repository.get_user_by_email(email)
    if user is not None:
        return user
    for candidate in repository.list_users():
        if candidate.role_id == role_id and candidate.client_id is None:
            return candidate
    return None
