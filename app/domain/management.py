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


MANAGEMENT_ATTACHMENT_KINDS = frozenset({"image", "video", "file"})
# Extensions accepted for kind "file" (images and videos are validated by kind only).
MANAGEMENT_FILE_EXTENSIONS = frozenset(
    {".pdf", ".xlsx", ".xls", ".doc", ".docx", ".csv", ".txt", ".jpg", ".jpeg", ".png"},
)


@dataclass(frozen=True)
class ManagementAttachmentRecord:
    """One image, video, or file on a task or on one of its messages (url may be a data URL)."""

    id: str
    task_id: str
    kind: str
    name: str
    url: str
    message_id: str | None = None


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
    attachments: tuple[ManagementAttachmentRecord, ...] = ()


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
    # Files added when the task was opened (message_id is None on each).
    attachments: tuple[ManagementAttachmentRecord, ...] = ()


class TaskNotFound(Exception):
    """Raised when a management task id does not exist."""


class InvalidManagementAttachment(ValueError):
    """Raised when an attachment has an unknown kind, no data, or a file type that is not allowed."""

    def __init__(self) -> None:
        super().__init__("Attachments must be images, videos, or .pdf .xlsx .doc .jpg files.")


IMPORT_STATUS_PENDING = "pending"
IMPORT_STATUS_APPROVED = "approved"
IMPORT_STATUS_REJECTED = "rejected"
IMPORT_STATUS_REVOKED = "revoked"
ALLOWED_IMPORT_STATUSES = frozenset(
    {
        IMPORT_STATUS_PENDING,
        IMPORT_STATUS_APPROVED,
        IMPORT_STATUS_REJECTED,
        IMPORT_STATUS_REVOKED,
    },
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


@dataclass(frozen=True)
class BuildingAdministratorRecord:
    """Administrator history row for the building owner's Administración screen."""

    user_id: str
    full_name: str
    email: str
    home: bool
    import_id: str | None
    status: str
    created_at: str
    resolved_at: str | None
