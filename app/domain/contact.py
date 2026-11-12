"""Contact message domain records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ContactMessageRecord:
    """One public contact submission."""

    id: str
    name: str
    email: str
    message: str
    privacy_accepted: bool
    privacy_accepted_at: str | None
    created_at: str
    subject: str = ""


class PrivacyConsentRequired(Exception):
    """Raised when the Chilean privacy checkbox was not accepted."""
