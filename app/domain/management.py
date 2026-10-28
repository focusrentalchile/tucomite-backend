"""Management task records shared by services and repositories."""

from dataclasses import dataclass

# Board columns. New tasks always start in todo.
MANAGEMENT_STATUS_TODO = "todo"
MANAGEMENT_STATUS_IN_PROGRESS = "in_progress"
MANAGEMENT_STATUS_DONE = "done"
ALLOWED_MANAGEMENT_STATUSES = frozenset(
    {MANAGEMENT_STATUS_TODO, MANAGEMENT_STATUS_IN_PROGRESS, MANAGEMENT_STATUS_DONE},
)
LEGACY_MANAGEMENT_STATUS_MAP = {
    "open": MANAGEMENT_STATUS_TODO,
    "pending": MANAGEMENT_STATUS_IN_PROGRESS,
    "resolved": MANAGEMENT_STATUS_DONE,
    "closed": MANAGEMENT_STATUS_DONE,
}


@dataclass(frozen=True)
class ManagementMessageRecord:
    """One message inside a management task."""

    id: str
    task_id: str
    author_user_id: str
    author_name: str
    body: str
    created_at: str
    from_staff: bool


@dataclass(frozen=True)
class ManagementTaskRecord:
    """A building management task handled on the three-column board."""

    id: str
    client_id: str | None
    client_name: str
    created_by_user_id: str
    created_by_name: str
    subject: str
    status: str
    priority_id: int
    due_date: str | None
    assignee_user_id: str | None
    topic_id: str | None
    created_at: str
    updated_at: str
    messages: tuple[ManagementMessageRecord, ...] = ()


class TaskNotFound(Exception):
    """Raised when a management task id does not exist."""


IMPORT_STATUS_PENDING = "pending"
IMPORT_STATUS_APPROVED = "approved"
IMPORT_STATUS_REJECTED = "rejected"
ALLOWED_IMPORT_STATUSES = frozenset(
    {IMPORT_STATUS_PENDING, IMPORT_STATUS_APPROVED, IMPORT_STATUS_REJECTED},
)


@dataclass(frozen=True)
class ManagementWorkspaceClientRecord:
    """One building available on an administrator's Gestión board."""

    client_id: str
    client_name: str
    home: bool


@dataclass(frozen=True)
class ManagementWorkspaceImportRecord:
    """Request to import a building into an administrator's Gestión workspace."""

    id: str
    administrator_user_id: str
    administrator_name: str
    administrator_email: str
    client_id: str
    client_name: str
    status: str
    created_at: str
    resolved_at: str | None
