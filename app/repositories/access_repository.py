"""MySQL repository for the access catalog, roles, and users."""

from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.access import ModuleDefinition, ModuleRecord, RoleRecord, UserRecord, permission_key
from app.models.access import FunctionalityModel, ModuleModel, RoleModel, RolePermissionModel, UserModel


class AccessRepository(Protocol):
    """Persistence port used by the access services."""

    def replace_catalog(self, modules: tuple[ModuleDefinition, ...]) -> None:
        """Replace the stored catalog with the modules registered in code."""

    def list_modules(self) -> list[ModuleRecord]:
        """Return modules with their functionalities in display order."""

    def list_roles(self) -> list[RoleRecord]:
        """Return every role."""

    def get_role(self, role_id: str) -> RoleRecord | None:
        """Return one role, or None."""

    def get_system_role(self) -> RoleRecord | None:
        """Return the seeded super-admin role, or None."""

    def add_role(self, role: RoleRecord) -> None:
        """Insert a role and its permissions."""

    def save_role(self, role: RoleRecord) -> None:
        """Replace a role's stored permissions."""

    def delete_role(self, role_id: str) -> None:
        """Delete one role and its permissions."""

    def count_users_with_role(self, role_id: str) -> int:
        """Return how many users hold this role."""

    def delete_users_with_role(self, role_id: str) -> int:
        """Delete every user that holds this role. Return how many were removed."""

    def list_users(self) -> list[UserRecord]:
        """Return every user."""

    def get_user(self, user_id: str) -> UserRecord | None:
        """Return one user by id."""

    def add_user(self, user: UserRecord) -> None:
        """Insert a user."""

    def save_user(self, user: UserRecord) -> None:
        """Update one stored user."""

    def delete_user(self, user_id: str) -> None:
        """Delete one user and related committee membership."""

    def close_user_account(self, user_id: str, closed_at: str) -> None:
        """Mark one user as closed (soft delete). The row and its history stay."""

    def get_user_by_email(self, email: str) -> UserRecord | None:
        """Return the user with this email, or None."""


class SqlAccessRepository:
    """SQLAlchemy adapter for the MySQL access tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_catalog(self, modules: tuple[ModuleDefinition, ...]) -> None:
        wanted = {
            (module.key, functionality)
            for module in modules
            for functionality in module.functionalities
        }
        for permission in self._session.scalars(select(RolePermissionModel)).all():
            if (permission.module_key, permission.functionality_key) not in wanted:
                self._session.delete(permission)
        self._session.flush()

        existing = {row.key: row for row in self._session.scalars(select(ModuleModel)).all()}
        keep = {module.key for module in modules}
        for index, module in enumerate(modules):
            row = existing.get(module.key)
            if row is None:
                row = ModuleModel(key=module.key, sort_order=index)
                self._session.add(row)
                self._session.flush()
            else:
                row.sort_order = index
            current = {item.key: item for item in row.functionalities}
            for fn_index, functionality in enumerate(module.functionalities):
                stored = current.get(functionality)
                if stored is None:
                    self._session.add(
                        FunctionalityModel(
                            module_key=module.key,
                            key=functionality,
                            sort_order=fn_index,
                        ),
                    )
                else:
                    stored.sort_order = fn_index
            for functionality, stored in current.items():
                if functionality not in module.functionalities:
                    self._session.delete(stored)
        for key, row in existing.items():
            if key not in keep:
                self._session.delete(row)
        self._session.flush()

    def list_modules(self) -> list[ModuleRecord]:
        rows = self._session.scalars(select(ModuleModel).order_by(ModuleModel.sort_order)).all()
        return [
            ModuleRecord(
                key=row.key,
                functionalities=tuple(
                    item.key
                    for item in sorted(row.functionalities, key=lambda item: item.sort_order)
                ),
            )
            for row in rows
        ]

    def list_roles(self) -> list[RoleRecord]:
        rows = self._session.scalars(select(RoleModel).order_by(RoleModel.is_system.desc(), RoleModel.name)).all()
        return [self._role(row) for row in rows]

    def get_role(self, role_id: str) -> RoleRecord | None:
        row = self._session.get(RoleModel, role_id)
        if row is None:
            return None
        return self._role(row)

    def get_system_role(self) -> RoleRecord | None:
        row = self._session.scalar(select(RoleModel).where(RoleModel.is_system.is_(True)))
        if row is None:
            return None
        return self._role(row)

    def add_role(self, role: RoleRecord) -> None:
        self._session.add(RoleModel(id=role.id, name=role.name, is_system=role.system))
        self._session.flush()
        self._insert_permissions(role)
        self._session.flush()

    def save_role(self, role: RoleRecord) -> None:
        row = self._session.get(RoleModel, role.id)
        if row is None:
            return
        row.name = role.name
        row.is_system = role.system
        self._session.execute(delete(RolePermissionModel).where(RolePermissionModel.role_id == role.id))
        self._insert_permissions(role)
        self._session.flush()

    def delete_role(self, role_id: str) -> None:
        row = self._session.get(RoleModel, role_id)
        if row is None:
            return
        self._session.execute(delete(RolePermissionModel).where(RolePermissionModel.role_id == role_id))
        self._session.delete(row)
        self._session.flush()

    def count_users_with_role(self, role_id: str) -> int:
        rows = self._session.scalars(select(UserModel).where(UserModel.role_id == role_id)).all()
        return len(rows)

    def delete_users_with_role(self, role_id: str) -> int:
        rows = self._session.scalars(select(UserModel).where(UserModel.role_id == role_id)).all()
        removed = 0
        for row in rows:
            self.delete_user(row.id)
            removed += 1
        return removed

    def list_users(self) -> list[UserRecord]:
        rows = self._session.scalars(select(UserModel).order_by(UserModel.full_name)).all()
        return [self._user(row) for row in rows]

    def get_user(self, user_id: str) -> UserRecord | None:
        row = self._session.get(UserModel, user_id)
        if row is None:
            return None
        return self._user(row)

    def add_user(self, user: UserRecord) -> None:
        self._session.add(
            UserModel(
                id=user.id,
                full_name=user.full_name,
                email=user.email,
                password_hash=user.password_hash,
                role_id=user.role_id,
                client_id=user.client_id,
                period_id=user.period_id,
                floor_number=user.floor_number,
                apartment_number=user.apartment_number,
            ),
        )
        self._session.flush()

    def save_user(self, user: UserRecord) -> None:
        row = self._session.get(UserModel, user.id)
        if row is None:
            return
        row.full_name = user.full_name
        row.email = user.email
        row.password_hash = user.password_hash
        row.role_id = user.role_id
        row.client_id = user.client_id
        row.period_id = user.period_id
        row.floor_number = user.floor_number
        row.apartment_number = user.apartment_number
        self._session.flush()

    def delete_user(self, user_id: str) -> None:
        """Delete a user and every row that still points at them with a FK."""
        from app.models.committee import CommitteeMemberModel
        from app.models.management import (
            ManagementAttachmentModel,
            ManagementMessageModel,
            ManagementTaskModel,
            ManagementWorkspaceImportModel,
        )
        from app.models.messages import (
            ResidentMessageAttachmentModel,
            ResidentMessageModel,
            ResidentMessageParticipantModel,
            ResidentMessageReplyModel,
            ResidentMessageStatusEventModel,
        )
        from app.models.notifications import NotificationModel

        member = self._session.get(CommitteeMemberModel, user_id)
        if member is not None:
            self._session.delete(member)

        self._session.execute(delete(NotificationModel).where(NotificationModel.user_id == user_id))
        self._session.execute(
            delete(ResidentMessageParticipantModel).where(
                ResidentMessageParticipantModel.user_id == user_id,
            ),
        )
        self._session.execute(
            delete(ManagementWorkspaceImportModel).where(
                ManagementWorkspaceImportModel.administrator_user_id == user_id,
            ),
        )
        authored_management_ids = self._session.scalars(
            select(ManagementMessageModel.id).where(ManagementMessageModel.author_user_id == user_id),
        ).all()
        if authored_management_ids:
            self._session.execute(
                delete(ManagementAttachmentModel).where(
                    ManagementAttachmentModel.message_id.in_(authored_management_ids),
                ),
            )
        self._session.execute(
            delete(ManagementMessageModel).where(ManagementMessageModel.author_user_id == user_id),
        )
        for task in self._session.scalars(
            select(ManagementTaskModel).where(ManagementTaskModel.assignee_user_id == user_id),
        ).all():
            task.assignee_user_id = None
        owned_tasks = self._session.scalars(
            select(ManagementTaskModel).where(ManagementTaskModel.created_by_user_id == user_id),
        ).all()
        for task in owned_tasks:
            self._session.execute(
                delete(ManagementAttachmentModel).where(ManagementAttachmentModel.task_id == task.id),
            )
            self._session.execute(
                delete(ManagementMessageModel).where(ManagementMessageModel.task_id == task.id),
            )
            self._session.delete(task)

        self._session.execute(
            delete(ResidentMessageReplyModel).where(ResidentMessageReplyModel.author_user_id == user_id),
        )
        authored_messages = self._session.scalars(
            select(ResidentMessageModel).where(ResidentMessageModel.author_user_id == user_id),
        ).all()
        for message in authored_messages:
            self._session.execute(
                delete(ResidentMessageAttachmentModel).where(
                    ResidentMessageAttachmentModel.message_id == message.id,
                ),
            )
            reply_ids = self._session.scalars(
                select(ResidentMessageReplyModel.id).where(
                    ResidentMessageReplyModel.message_id == message.id,
                ),
            ).all()
            if reply_ids:
                self._session.execute(
                    delete(ResidentMessageAttachmentModel).where(
                        ResidentMessageAttachmentModel.reply_id.in_(reply_ids),
                    ),
                )
            self._session.execute(
                delete(ResidentMessageReplyModel).where(ResidentMessageReplyModel.message_id == message.id),
            )
            self._session.execute(
                delete(ResidentMessageStatusEventModel).where(
                    ResidentMessageStatusEventModel.message_id == message.id,
                ),
            )
            self._session.delete(message)

        row = self._session.get(UserModel, user_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    def close_user_account(self, user_id: str, closed_at: str) -> None:
        row = self._session.get(UserModel, user_id)
        if row is None:
            return
        parsed = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        row.account_closed_at = parsed
        self._session.flush()

    def get_user_by_email(self, email: str) -> UserRecord | None:
        row = self._session.scalar(select(UserModel).where(UserModel.email == email))
        if row is None:
            return None
        return self._user(row)

    def _insert_permissions(self, role: RoleRecord) -> None:
        for key in sorted(role.permissions):
            module_key, functionality_key = key.split(".", 1)
            self._session.add(
                RolePermissionModel(
                    role_id=role.id,
                    module_key=module_key,
                    functionality_key=functionality_key,
                ),
            )

    def _role(self, row: RoleModel) -> RoleRecord:
        return RoleRecord(
            id=row.id,
            name=row.name,
            system=row.is_system,
            permissions=frozenset(
                permission_key(item.module_key, item.functionality_key) for item in row.permissions
            ),
        )

    def _user(self, row: UserModel) -> UserRecord:
        return UserRecord(
            id=row.id,
            full_name=row.full_name,
            email=row.email,
            password_hash=row.password_hash,
            role_id=row.role_id,
            client_id=getattr(row, "client_id", None),
            period_id=getattr(row, "period_id", None),
            floor_number=getattr(row, "floor_number", None),
            apartment_number=getattr(row, "apartment_number", None),
            account_closed_at=(
                closed.replace(tzinfo=timezone.utc).isoformat()
                if (closed := getattr(row, "account_closed_at", None)) is not None
                else None
            ),
        )
