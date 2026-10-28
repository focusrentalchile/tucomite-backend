"""Registers the modules that exist in the product today.

Add a module here when its functionalities are implemented.
Startup syncs this registry into MySQL, and the admin matrix reads it back.
"""

from app.core.access_catalog import access_catalog
from app.domain.access import ModuleDefinition


def register_builtin_modules() -> None:
    """Register the modules shipped with this build."""
    if access_catalog.modules():
        return
    access_catalog.register(ModuleDefinition(key="users", functionalities=("view", "create")))
    access_catalog.register(
        ModuleDefinition(key="roles", functionalities=("view", "create", "update")),
    )
    access_catalog.register(ModuleDefinition(key="agreements", functionalities=("view", "vote")))
    access_catalog.register(ModuleDefinition(key="matters", functionalities=("create", "comment")))
    access_catalog.register(ModuleDefinition(key="tasks", functionalities=("assign",)))
    access_catalog.register(ModuleDefinition(key="progress", functionalities=("view", "update")))
    access_catalog.register(ModuleDefinition(key="documents", functionalities=("view",)))
    access_catalog.register(ModuleDefinition(key="notifications", functionalities=("receive",)))


register_builtin_modules()
