"""Account closure (baja) records and errors for building owners."""

from dataclasses import dataclass

CLIENT_ROLE_NAME = "client"


@dataclass(frozen=True)
class AccountClosureRequestRecord:
    """Why and when a building owner closed their account."""

    id: str
    user_id: str
    client_id: str | None
    reason: str
    created_at: str


@dataclass(frozen=True)
class AccountExport:
    """The ZIP produced for a closing account."""

    filename: str
    content: bytes


class AccountNotClient(Exception):
    """Raised when someone other than the building owner (client role) closes an account."""


class InvalidAccountPassword(Exception):
    """Raised when the confirmation password does not match."""


class AccountAlreadyClosed(Exception):
    """Raised when the account was already closed."""
