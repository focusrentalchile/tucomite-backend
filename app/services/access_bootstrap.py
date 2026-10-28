"""Seeds the super admin, demo client, and keeps the MySQL catalog aligned with code."""

import uuid
from datetime import date, timedelta

from app.core.access_catalog import AccessCatalog
from app.domain.access import SUPER_ADMIN_EMAIL, ClientRecord, RoleRecord, UserRecord
from app.repositories.access_repository import AccessRepository
from app.repositories.client_repository import ClientRepository
from app.utils.passwords import hash_password

SEED_PASSWORD = "123456"
DEMO_CLIENT_NAME = "Cliente de prueba"
DEMO_ADMIN_EMAIL = "admin@demo.tucomite.local"
DEMO_ADMIN_NAME = "Admin de prueba"

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
        }
    ),
    "resident": frozenset(
        {
            "agreements.view",
            "progress.view",
            "documents.view",
            "notifications.receive",
        }
    ),
}


def bootstrap_access(
    repository: AccessRepository,
    catalog: AccessCatalog,
    clients: ClientRepository | None = None,
) -> None:
    """Sync modules, keep the system role complete, and seed demo accounts."""
    repository.replace_catalog(catalog.modules())
    keys = catalog.permission_keys()
    role = repository.get_system_role()
    if role is None:
        role = RoleRecord(
            id=str(uuid.uuid4()),
            name="Super admin",
            system=True,
            permissions=keys,
        )
        repository.add_role(role)
        repository.add_user(
            UserRecord(
                id=str(uuid.uuid4()),
                full_name="Super admin",
                email=SUPER_ADMIN_EMAIL,
                password_hash=hash_password(SEED_PASSWORD),
                role_id=role.id,
                client_id=None,
            ),
        )
    else:
        if role.permissions != keys:
            repository.save_role(RoleRecord(id=role.id, name=role.name, system=True, permissions=keys))
        _ensure_super_admin_user(repository, role.id)
    _ensure_starter_roles(repository, keys)
    if clients is not None:
        _ensure_demo_client(repository, clients)


def _ensure_super_admin_user(repository: AccessRepository, role_id: str) -> None:
    """Keep the seeded super admin email and password in sync."""
    user = repository.get_user_by_email(SUPER_ADMIN_EMAIL)
    if user is None:
        repository.add_user(
            UserRecord(
                id=str(uuid.uuid4()),
                full_name="Super admin",
                email=SUPER_ADMIN_EMAIL,
                password_hash=hash_password(SEED_PASSWORD),
                role_id=role_id,
                client_id=None,
            ),
        )
        return
    repository.save_user(
        UserRecord(
            id=user.id,
            full_name=user.full_name or "Super admin",
            email=SUPER_ADMIN_EMAIL,
            password_hash=hash_password(SEED_PASSWORD),
            role_id=role_id,
            client_id=None,
        ),
    )


def _ensure_starter_roles(repository: AccessRepository, keys: frozenset[str]) -> None:
    """Add each building group when it is missing and the catalog knows its actions."""
    existing = {role.name.casefold() for role in repository.list_roles()}
    for name, permissions in STARTER_ROLES.items():
        if name.casefold() in existing:
            continue
        allowed = frozenset(permission for permission in permissions if permission in keys)
        if not allowed:
            continue
        repository.add_role(
            RoleRecord(id=str(uuid.uuid4()), name=name, system=False, permissions=allowed),
        )


def _ensure_demo_client(repository: AccessRepository, clients: ClientRepository) -> None:
    """Seed one demo client and its administrator when missing."""
    today = date.today()
    starts = today.isoformat()
    ends = (today + timedelta(days=365)).isoformat()
    existing = clients.get_client_by_name(DEMO_CLIENT_NAME)
    if existing is not None:
        if not existing.license_starts_at or not existing.license_ends_at:
            clients.save_client(
                ClientRecord(
                    id=existing.id,
                    name=existing.name,
                    admin_user_id=existing.admin_user_id,
                    license_starts_at=starts,
                    license_ends_at=ends,
                ),
            )
        return
    if repository.get_user_by_email(DEMO_ADMIN_EMAIL) is not None:
        return
    admin_role = next(
        (role for role in repository.list_roles() if role.name.casefold() == "administrator"),
        None,
    )
    if admin_role is None:
        return
    client_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    repository.add_user(
        UserRecord(
            id=user_id,
            full_name=DEMO_ADMIN_NAME,
            email=DEMO_ADMIN_EMAIL,
            password_hash=hash_password(SEED_PASSWORD),
            role_id=admin_role.id,
            client_id=client_id,
        ),
    )
    clients.add_client(
        ClientRecord(
            id=client_id,
            name=DEMO_CLIENT_NAME,
            admin_user_id=user_id,
            license_starts_at=starts,
            license_ends_at=ends,
        ),
    )
