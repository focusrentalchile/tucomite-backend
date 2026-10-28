"""Access-control records shared by services and repositories."""

from dataclasses import dataclass


SUPER_ADMIN_EMAIL = "admin@tucomite.local"


@dataclass(frozen=True)
class ModuleDefinition:
    """One product module and the functionalities it exposes."""

    key: str
    functionalities: tuple[str, ...]


@dataclass(frozen=True)
class ModuleRecord:
    """Catalog row read back from persistence."""

    key: str
    functionalities: tuple[str, ...]


@dataclass(frozen=True)
class RoleRecord:
    """A named set of permission keys."""

    id: str
    name: str
    system: bool
    permissions: frozenset[str]


@dataclass(frozen=True)
class UserRecord:
    """A person who can sign in and holds one role."""

    id: str
    full_name: str
    email: str
    password_hash: str
    role_id: str


class RoleNotFound(Exception):
    """Raised when a role id does not exist."""


class DuplicateRoleName(Exception):
    """Raised when a role name is already taken."""


class UnknownPermission(Exception):
    """Raised when a module or functionality is not in the catalog."""


class ProtectedRole(Exception):
    """Raised when a system role would lose its fixed permissions."""


class DuplicateEmail(Exception):
    """Raised when an email is already registered."""


class UnknownRole(Exception):
    """Raised when a user is assigned a missing role."""


class UserNotFound(Exception):
    """Raised when a user id does not exist."""


class ProtectedUser(Exception):
    """Raised when the seeded super admin would be removed."""


def permission_key(module_key: str, functionality_key: str) -> str:
    """Build the stable key stored for one checkbox."""
    return f"{module_key}.{functionality_key}"
