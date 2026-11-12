"""Domain records for invitations."""

from dataclasses import dataclass


KIND_PLATFORM = "platform"
KIND_BUILDING = "building"

STATUS_FAILED = "failed"
STATUS_SENT = "sent"
STATUS_OPENED = "opened"
STATUS_REGISTERED = "registered"


@dataclass(frozen=True)
class InvitationRecord:
    """One invitation row."""

    id: str
    kind: str
    name: str
    email: str
    building_name: str
    role_key: str
    client_id: str | None
    invited_by_user_id: str
    token: str
    sent_at: str | None
    opened_at: str | None
    registered_at: str | None
    created_at: str

    @property
    def status(self) -> str:
        if self.registered_at:
            return STATUS_REGISTERED
        if self.opened_at:
            return STATUS_OPENED
        if self.sent_at:
            return STATUS_SENT
        return STATUS_FAILED


class InvitationNotFound(Exception):
    """Raised when an invitation id or token does not exist."""


class InvitationAlreadyUsed(Exception):
    """Raised when registration is attempted on a used invitation."""


class InvitationForbidden(Exception):
    """Raised when the actor cannot manage the invitation."""


class InvitationEmailFailed(Exception):
    """Raised when the invitation row was prepared but SMTP delivery failed."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
