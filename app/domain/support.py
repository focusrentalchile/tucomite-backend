"""Support ticket records shared by services and repositories."""

from dataclasses import dataclass

# Board columns. New tickets always start in todo.
SUPPORT_STATUS_TODO = "todo"
SUPPORT_STATUS_IN_PROGRESS = "in_progress"
SUPPORT_STATUS_DONE = "done"
ALLOWED_SUPPORT_STATUSES = frozenset(
    {SUPPORT_STATUS_TODO, SUPPORT_STATUS_IN_PROGRESS, SUPPORT_STATUS_DONE},
)
LEGACY_SUPPORT_STATUS_MAP = {
    "open": SUPPORT_STATUS_TODO,
    "pending": SUPPORT_STATUS_IN_PROGRESS,
    "resolved": SUPPORT_STATUS_DONE,
    "closed": SUPPORT_STATUS_DONE,
}


@dataclass(frozen=True)
class SupportMessageRecord:
    """One message inside a support ticket."""

    id: str
    ticket_id: str
    author_user_id: str
    author_name: str
    body: str
    created_at: str
    from_staff: bool


@dataclass(frozen=True)
class SupportTicketRecord:
    """A building support task handled on the three-column board."""

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
    messages: tuple[SupportMessageRecord, ...] = ()


class TicketNotFound(Exception):
    """Raised when a support ticket id does not exist."""
