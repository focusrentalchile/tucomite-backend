"""Legal cases for a building (client / committee)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LegalCaseAttachmentRecord:
    """One file attached to a legal case."""

    id: str
    case_id: str
    kind: str
    name: str
    url: str


@dataclass(frozen=True)
class LegalCaseRecord:
    """A legal case owned by one building."""

    id: str
    client_id: str
    title: str
    description: str
    created_at: str
    created_by_user_id: str


class LegalCaseNotFound(Exception):
    """Raised when a legal case id does not exist for the building."""
