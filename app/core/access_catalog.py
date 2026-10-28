"""Registry of modules and functionalities the product currently exposes."""

from app.domain.access import ModuleDefinition, permission_key


class AccessCatalog:
    """In-memory registry. New modules are registered in code and synced to MySQL."""

    def __init__(self) -> None:
        self._modules: list[ModuleDefinition] = []

    def register(self, module: ModuleDefinition) -> None:
        """Add a module once. Later registrations of the same key are ignored."""
        if any(item.key == module.key for item in self._modules):
            return
        self._modules.append(module)

    def modules(self) -> tuple[ModuleDefinition, ...]:
        """Return modules in registration order."""
        return tuple(self._modules)

    def has(self, module_key: str, functionality_key: str) -> bool:
        """Report whether the catalog contains this checkbox."""
        return any(
            module.key == module_key and functionality_key in module.functionalities
            for module in self._modules
        )

    def permission_keys(self) -> frozenset[str]:
        """Return every module.functionality key in the catalog."""
        return frozenset(
            permission_key(module.key, functionality)
            for module in self._modules
            for functionality in module.functionalities
        )


access_catalog = AccessCatalog()
