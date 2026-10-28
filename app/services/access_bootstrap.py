"""Keeps the MySQL access catalog and starter roles aligned with code."""

import uuid
from datetime import date, timedelta

from app.core.access_catalog import AccessCatalog
from app.domain.access import ClientRecord, RoleRecord, UserRecord
from app.repositories.access_repository import AccessRepository
from app.repositories.client_repository import ClientRepository
from app.utils.passwords import hash_password

DEMO_CLIENT_NAME = "Cliente de prueba"

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
            "users.view",
            "users.create",
            "support.view",
            "support.create",
            "support.reply",
            "support.update",
            "notifications.receive",
        }
    ),
    "resident": frozenset(
        {
            "notifications.receive",
        }
    ),
    # Building owner. Hidden from the roles list; can do everything except Gestión (support).
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

# Starter roles that exist in the catalog but stay out of the Roles screen.
HIDDEN_ROLES: frozenset[str] = frozenset({"client"})


def bootstrap_access(
    repository: AccessRepository,
    catalog: AccessCatalog,
    clients: ClientRepository | None = None,
) -> None:
    """Sync modules and starter roles. Platform users are stored only in the database."""
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
        _ensure_building_owners_use_client_role(repository, clients)


def upsert_platform_accounts(
    repository: AccessRepository,
    clients: ClientRepository,
    *,
    super_admin_email: str,
    super_admin_password: str,
    demo_admin_email: str,
    demo_admin_password: str,
    demo_client_name: str = DEMO_CLIENT_NAME,
    demo_admin_name: str = "Admin de prueba",
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
                    full_name=demo_user.full_name or demo_admin_name,
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
                full_name=demo_user.full_name or demo_admin_name,
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
