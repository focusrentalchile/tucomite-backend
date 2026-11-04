"""Legal cases for a building (client / committee create; legal counsel works them)."""

from dataclasses import dataclass

LEGAL_STATUS_WAITING = "waiting"
LEGAL_STATUS_IN_PROGRESS = "in_progress"
LEGAL_STATUS_FINISHED = "finished"
LEGAL_STATUSES = frozenset(
    {LEGAL_STATUS_WAITING, LEGAL_STATUS_IN_PROGRESS, LEGAL_STATUS_FINISHED},
)


@dataclass(frozen=True)
class LegalCaseAttachmentRecord:
    """One file attached to a legal case."""

    id: str
    case_id: str
    kind: str
    name: str
    url: str


@dataclass(frozen=True)
class LegalCaseMessageRecord:
    """One message on a legal case thread."""

    id: str
    case_id: str
    author_user_id: str
    author_name: str
    body: str
    from_legal: bool
    created_at: str


@dataclass(frozen=True)
class LegalCaseRecord:
    """A legal case owned by one building."""

    id: str
    client_id: str
    title: str
    description: str
    created_at: str
    created_by_user_id: str
    status: str = LEGAL_STATUS_WAITING


class LegalCaseNotFound(Exception):
    """Raised when a legal case id does not exist for the building."""


class InvalidLegalStatus(Exception):
    """Raised when a status value is not allowed."""
