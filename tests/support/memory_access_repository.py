"""In-memory access repository for service unit tests."""

from app.domain.access import ModuleDefinition, ModuleRecord, RoleRecord, UserRecord


class InMemoryAccessRepository:
    """Stores catalog, roles, and users in process memory."""

    def __init__(self) -> None:
        self.modules: list[ModuleRecord] = []
        self.roles: list[RoleRecord] = []
        self.users: list[UserRecord] = []

    def replace_catalog(self, modules: tuple[ModuleDefinition, ...]) -> None:
        wanted = {
            (module.key, functionality)
            for module in modules
            for functionality in module.functionalities
        }
        self.modules = [
            ModuleRecord(key=module.key, functionalities=module.functionalities) for module in modules
        ]
        self.roles = [
            RoleRecord(
                id=role.id,
                name=role.name,
                system=role.system,
                permissions=frozenset(
                    key
                    for key in role.permissions
                    if tuple(key.split(".", 1)) in wanted
                ),
            )
            for role in self.roles
        ]

    def list_modules(self) -> list[ModuleRecord]:
        return list(self.modules)

    def list_roles(self) -> list[RoleRecord]:
        return sorted(self.roles, key=lambda role: (not role.system, role.name))

    def get_role(self, role_id: str) -> RoleRecord | None:
        return next((role for role in self.roles if role.id == role_id), None)

    def get_system_role(self) -> RoleRecord | None:
        return next((role for role in self.roles if role.system), None)

    def add_role(self, role: RoleRecord) -> None:
        self.roles.append(role)

    def save_role(self, role: RoleRecord) -> None:
        self.roles = [role if item.id == role.id else item for item in self.roles]

    def list_users(self) -> list[UserRecord]:
        return sorted(self.users, key=lambda user: user.full_name)

    def get_user(self, user_id: str) -> UserRecord | None:
        return next((user for user in self.users if user.id == user_id), None)

    def add_user(self, user: UserRecord) -> None:
        self.users.append(user)

    def save_user(self, user: UserRecord) -> None:
        self.users = [user if item.id == user.id else item for item in self.users]

    def delete_user(self, user_id: str) -> None:
        self.users = [user for user in self.users if user.id != user_id]

    def get_user_by_email(self, email: str) -> UserRecord | None:
        return next((user for user in self.users if user.email == email), None)
