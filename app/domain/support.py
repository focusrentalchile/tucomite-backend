"""Support ticket records shared by services and repositories."""

from dataclasses import dataclass


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
    """A building support request handled by platform staff."""

    id: str
    client_id: str | None
    client_name: str
    created_by_user_id: str
    created_by_name: str
    subject: str
    status: str
    created_at: str
    updated_at: str
    messages: tuple[SupportMessageRecord, ...] = ()


class TicketNotFound(Exception):
    """Raised when a support ticket id does not exist."""
