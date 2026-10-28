"""Persistence for management tasks and messages."""

from datetime import date, datetime, timezone
from typing import Protocol

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.domain.management import (
    IMPORT_STATUS_APPROVED,
    IMPORT_STATUS_PENDING,
    LEGACY_MANAGEMENT_STATUS_MAP,
    MANAGEMENT_STATUS_TODO,
    ManagementMessageRecord,
    ManagementTaskRecord,
    ManagementWorkspaceImportRecord,
)
from app.domain.topics import MEDIUM_PRIORITY_ID
from app.models.access import ClientModel, UserModel
from app.models.management import ManagementMessageModel, ManagementTaskModel, ManagementWorkspaceImportModel


class ManagementRepository(Protocol):
    """Persistence port used by the management service."""

    def list_tasks(
        self,
        *,
        client_id: str | None = None,
        client_ids: list[str] | None = None,
    ) -> list[ManagementTaskRecord]:
        """Return tickets for one building, a set of buildings, or every ticket."""

    def get_task(self, task_id: str) -> ManagementTaskRecord | None:
        """Return one ticket with messages."""

    def add_task(self, ticket: ManagementTaskRecord) -> None:
        """Insert a ticket and its first message when provided."""

    def add_message(self, message: ManagementMessageRecord) -> None:
        """Append one message and bump the ticket updated_at."""

    def save_task_status(self, task_id: str, status: str) -> None:
        """Update ticket status."""

    def list_approved_client_ids(self, administrator_user_id: str) -> list[str]:
        """Return client ids approved for this administrator's Gestión board."""

    def list_imports_for_administrator(self, administrator_user_id: str) -> list[ManagementWorkspaceImportRecord]:
        """Return import requests opened by this administrator."""

    def list_pending_imports_for_client(self, client_id: str) -> list[ManagementWorkspaceImportRecord]:
        """Return pending import requests targeting this building."""

    def get_import(self, import_id: str) -> ManagementWorkspaceImportRecord | None:
        """Return one import request."""

    def find_open_import(self, administrator_user_id: str, client_id: str) -> ManagementWorkspaceImportRecord | None:
        """Return a pending or approved import for this pair, if any."""

    def add_import(self, record: ManagementWorkspaceImportRecord) -> None:
        """Insert an import request."""

    def save_import_status(self, import_id: str, status: str, *, resolved_at: str) -> None:
        """Update import status and resolution time."""


class SqlManagementRepository:
    """SQLAlchemy adapter for management tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_tasks(
        self,
        *,
        client_id: str | None = None,
        client_ids: list[str] | None = None,
    ) -> list[ManagementTaskRecord]:
        query = select(ManagementTaskModel).order_by(ManagementTaskModel.updated_at.desc())
        if client_ids is not None:
            if not client_ids:
                return []
            query = query.where(ManagementTaskModel.client_id.in_(client_ids))
        elif client_id is not None:
            query = query.where(ManagementTaskModel.client_id == client_id)
        rows = self._session.execute(query).scalars().all()
        return [self._task(row, include_messages=False) for row in rows]

    def get_task(self, task_id: str) -> ManagementTaskRecord | None:
        row = self._session.get(ManagementTaskModel, task_id)
        if row is None:
            return None
        return self._task(row, include_messages=True)

    def add_task(self, ticket: ManagementTaskRecord) -> None:
        due = date.fromisoformat(ticket.due_date) if ticket.due_date else None
        self._session.add(
            ManagementTaskModel(
                id=ticket.id,
                client_id=ticket.client_id,
                created_by_user_id=ticket.created_by_user_id,
                subject=ticket.subject,
                status=ticket.status or MANAGEMENT_STATUS_TODO,
                priority_id=ticket.priority_id or MEDIUM_PRIORITY_ID,
                due_date=due,
                assignee_user_id=ticket.assignee_user_id,
                topic_id=ticket.topic_id,
            ),
        )
        self._session.flush()
        for message in ticket.messages:
            self.add_message(message)
        self._session.flush()

    def add_message(self, message: ManagementMessageRecord) -> None:
        self._session.add(
            ManagementMessageModel(
                id=message.id,
                task_id=message.task_id,
                author_user_id=message.author_user_id,
                body=message.body,
                from_staff=message.from_staff,
            ),
        )
        ticket = self._session.get(ManagementTaskModel, message.task_id)
        if ticket is not None:
            ticket.updated_at = datetime.now(timezone.utc)
        self._session.flush()

    def save_task_status(self, task_id: str, status: str) -> None:
        row = self._session.get(ManagementTaskModel, task_id)
        if row is None:
            raise KeyError(task_id)
        row.status = status
        row.updated_at = datetime.now(timezone.utc)

    def _task(self, row: ManagementTaskModel, *, include_messages: bool) -> ManagementTaskRecord:
        client_name = ""
        if row.client_id:
            client = self._session.get(ClientModel, row.client_id)
            client_name = client.name if client is not None else ""
        author = self._session.get(UserModel, row.created_by_user_id)
        status = LEGACY_MANAGEMENT_STATUS_MAP.get(row.status, row.status)
        messages: tuple[ManagementMessageRecord, ...] = ()
        if include_messages:
            message_rows = self._session.execute(
                select(ManagementMessageModel)
                .where(ManagementMessageModel.task_id == row.id)
                .order_by(ManagementMessageModel.created_at.asc(), ManagementMessageModel.id.asc()),
            ).scalars().all()
            messages = tuple(self._message(item) for item in message_rows)
        return ManagementTaskRecord(
            id=row.id,
            client_id=row.client_id,
            client_name=client_name,
            created_by_user_id=row.created_by_user_id,
            created_by_name=author.full_name if author is not None else "",
            subject=row.subject,
            status=status,
            priority_id=row.priority_id or MEDIUM_PRIORITY_ID,
            due_date=row.due_date.isoformat() if row.due_date else None,
            assignee_user_id=row.assignee_user_id,
            topic_id=row.topic_id,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
            messages=messages,
        )

    def _message(self, row: ManagementMessageModel) -> ManagementMessageRecord:
        author = self._session.get(UserModel, row.author_user_id)
        return ManagementMessageRecord(
            id=row.id,
            task_id=row.task_id,
            author_user_id=row.author_user_id,
            author_name=author.full_name if author is not None else "",
            body=row.body,
            created_at=row.created_at.isoformat() if row.created_at else "",
            from_staff=row.from_staff,
        )

    def list_approved_client_ids(self, administrator_user_id: str) -> list[str]:
        rows = self._session.execute(
            select(ManagementWorkspaceImportModel.client_id).where(
                ManagementWorkspaceImportModel.administrator_user_id == administrator_user_id,
                ManagementWorkspaceImportModel.status == IMPORT_STATUS_APPROVED,
            ),
        ).scalars().all()
        return list(rows)

    def list_imports_for_administrator(self, administrator_user_id: str) -> list[ManagementWorkspaceImportRecord]:
        rows = self._session.execute(
            select(ManagementWorkspaceImportModel)
            .where(ManagementWorkspaceImportModel.administrator_user_id == administrator_user_id)
            .order_by(ManagementWorkspaceImportModel.created_at.desc()),
        ).scalars().all()
        return [self._import(row) for row in rows]

    def list_pending_imports_for_client(self, client_id: str) -> list[ManagementWorkspaceImportRecord]:
        rows = self._session.execute(
            select(ManagementWorkspaceImportModel)
            .where(
                ManagementWorkspaceImportModel.client_id == client_id,
                ManagementWorkspaceImportModel.status == IMPORT_STATUS_PENDING,
            )
            .order_by(ManagementWorkspaceImportModel.created_at.desc()),
        ).scalars().all()
        return [self._import(row) for row in rows]

    def get_import(self, import_id: str) -> ManagementWorkspaceImportRecord | None:
        row = self._session.get(ManagementWorkspaceImportModel, import_id)
        if row is None:
            return None
        return self._import(row)

    def find_open_import(self, administrator_user_id: str, client_id: str) -> ManagementWorkspaceImportRecord | None:
        row = self._session.execute(
            select(ManagementWorkspaceImportModel)
            .where(
                ManagementWorkspaceImportModel.administrator_user_id == administrator_user_id,
                ManagementWorkspaceImportModel.client_id == client_id,
                ManagementWorkspaceImportModel.status.in_((IMPORT_STATUS_PENDING, IMPORT_STATUS_APPROVED)),
            )
            .limit(1),
        ).scalar_one_or_none()
        if row is None:
            return None
        return self._import(row)

    def add_import(self, record: ManagementWorkspaceImportRecord) -> None:
        self._session.add(
            ManagementWorkspaceImportModel(
                id=record.id,
                administrator_user_id=record.administrator_user_id,
                client_id=record.client_id,
                status=record.status or IMPORT_STATUS_PENDING,
            ),
        )
        self._session.flush()

    def save_import_status(self, import_id: str, status: str, *, resolved_at: str) -> None:
        row = self._session.get(ManagementWorkspaceImportModel, import_id)
        if row is None:
            raise KeyError(import_id)
        row.status = status
        row.resolved_at = datetime.fromisoformat(resolved_at)
        self._session.flush()

    def _import(self, row: ManagementWorkspaceImportModel) -> ManagementWorkspaceImportRecord:
        admin = self._session.get(UserModel, row.administrator_user_id)
        client = self._session.get(ClientModel, row.client_id)
        return ManagementWorkspaceImportRecord(
            id=row.id,
            administrator_user_id=row.administrator_user_id,
            administrator_name=admin.full_name if admin is not None else "",
            administrator_email=admin.email if admin is not None else "",
            client_id=row.client_id,
            client_name=client.name if client is not None else "",
            status=row.status,
            created_at=row.created_at.isoformat() if row.created_at else "",
            resolved_at=row.resolved_at.isoformat() if row.resolved_at else None,
        )


def _table_exists(connection, table_name: str) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() "
                f"AND TABLE_NAME = '{table_name}'"
            ),
        ).scalar(),
    )


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                f"AND TABLE_NAME = '{table_name}' AND COLUMN_NAME = '{column_name}'"
            ),
        ).scalar(),
    )


def ensure_management_schema(connection) -> None:
    """Rename legacy support/gestion tables and keep management columns up to date."""
    renames = (
        ("support_tickets", "gestion_tasks"),
        ("gestion_tasks", "management_tasks"),
        ("support_messages", "gestion_messages"),
        ("gestion_messages", "management_messages"),
        ("support_workspace_imports", "gestion_workspace_imports"),
        ("gestion_workspace_imports", "management_workspace_imports"),
    )
    for old_name, new_name in renames:
        if _table_exists(connection, old_name) and not _table_exists(connection, new_name):
            connection.execute(text(f"RENAME TABLE `{old_name}` TO `{new_name}`"))
    if _table_exists(connection, "management_messages") and _column_exists(
        connection,
        "management_messages",
        "ticket_id",
    ) and not _column_exists(connection, "management_messages", "task_id"):
        connection.execute(
            text("ALTER TABLE `management_messages` CHANGE COLUMN `ticket_id` `task_id` VARCHAR(36) NOT NULL"),
        )
    if not _table_exists(connection, "management_tasks"):
        return
    for column, ddl in (
        ("priority_id", "ALTER TABLE `management_tasks` ADD COLUMN `priority_id` INT NOT NULL DEFAULT 2"),
        ("due_date", "ALTER TABLE `management_tasks` ADD COLUMN `due_date` DATE NULL"),
        ("assignee_user_id", "ALTER TABLE `management_tasks` ADD COLUMN `assignee_user_id` VARCHAR(36) NULL"),
        ("topic_id", "ALTER TABLE `management_tasks` ADD COLUMN `topic_id` VARCHAR(36) NULL"),
    ):
        if not _column_exists(connection, "management_tasks", column):
            connection.execute(text(ddl))
    connection.execute(
        text(
            "UPDATE `management_tasks` SET `status` = 'todo' "
            "WHERE `status` IN ('open')"
        ),
    )
    connection.execute(
        text(
            "UPDATE `management_tasks` SET `status` = 'in_progress' "
            "WHERE `status` IN ('pending')"
        ),
    )
    connection.execute(
        text(
            "UPDATE `management_tasks` SET `status` = 'done' "
            "WHERE `status` IN ('resolved', 'closed')"
        ),
    )
