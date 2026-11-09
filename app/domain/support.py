"""Domain records for platform support tickets."""

from dataclasses import dataclass

SUPPORT_STATUS_OPEN = "open"
SUPPORT_STATUS_ANSWERED = "answered"
SUPPORT_STATUS_CLOSED = "closed"

SUPPORT_STATUSES = frozenset(
    {
        SUPPORT_STATUS_OPEN,
        SUPPORT_STATUS_ANSWERED,
        SUPPORT_STATUS_CLOSED,
    }
)

# 1 = Soporte (building users). 2 = Mensaje (public web contact).
SUPPORT_TYPE_SUPPORT = "Soporte"
SUPPORT_TYPE_MESSAGE = "Mensaje"

# Legacy names renamed on bootstrap so existing rows keep working.
LEGACY_SUPPORT_TYPE_RENAMES = {
    "Soporte tipo 1": SUPPORT_TYPE_SUPPORT,
    "Soporte tipo 2": SUPPORT_TYPE_SUPPORT,
}

DEFAULT_SUPPORT_TYPE_NAMES = (SUPPORT_TYPE_SUPPORT, SUPPORT_TYPE_MESSAGE)
CREATABLE_SUPPORT_TYPE_NAMES = frozenset({SUPPORT_TYPE_SUPPORT})


@dataclass(frozen=True)
class SupportTypeRecord:
    """One selectable support ticket type."""

    id: str
    name: str


@dataclass(frozen=True)
class SupportAttachmentRecord:
    """One file attached to a support ticket."""

    id: str
    ticket_id: str
    kind: str
    name: str
    url: str


@dataclass(frozen=True)
class SupportReplyRecord:
    """One reply in a support ticket chat."""

    id: str
    ticket_id: str
    author_user_id: str | None
    author_name: str
    body: str
    from_staff: bool
    created_at: str


@dataclass(frozen=True)
class SupportTicketRecord:
    """One platform support ticket."""

    id: str
    support_type_id: str
    support_type_name: str
    subject: str
    body: str
    status: str
    created_at: str
    updated_at: str
    client_id: str | None = None
    author_user_id: str | None = None
    author_name: str = ""
    contact_name: str | None = None
    contact_email: str | None = None
    attachments: tuple[SupportAttachmentRecord, ...] = ()
    replies: tuple[SupportReplyRecord, ...] = ()


class SupportTicketNotFound(Exception):
    """Raised when a support ticket id does not exist."""


class SupportTypeNotFound(Exception):
    """Raised when a support type id does not exist."""


class InvalidSupportType(Exception):
    """Raised when a type cannot be used for the requested action."""


class SupportEmailError(Exception):
    """Raised when a web-message reply email cannot be sent."""
