"""Seeds the super admin and keeps the MySQL catalog aligned with code."""

import uuid

from app.core.access_catalog import AccessCatalog
from app.domain.access import SUPER_ADMIN_EMAIL, RoleRecord, UserRecord
from app.repositories.access_repository import AccessRepository
from app.utils.passwords import hash_password

SEED_PASSWORD = "super-admin"

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


def bootstrap_access(repository: AccessRepository, catalog: AccessCatalog) -> None:
    """Sync modules, keep the system role complete, and add the building groups once."""
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
            ),
        )
    elif role.permissions != keys:
        repository.save_role(RoleRecord(id=role.id, name=role.name, system=True, permissions=keys))
    _ensure_starter_roles(repository, keys)


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
