"""Domain records for invitations."""

from dataclasses import dataclass


KIND_PLATFORM = "platform"
KIND_BUILDING = "building"

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
        return STATUS_SENT


class InvitationNotFound(Exception):
    """Raised when an invitation id or token does not exist."""


class InvitationAlreadyUsed(Exception):
    """Raised when registration is attempted on a used invitation."""


class InvitationForbidden(Exception):
    """Raised when the actor cannot manage the invitation."""
