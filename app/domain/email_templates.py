"""Domain records for editable transactional email templates."""

from dataclasses import dataclass

TEMPLATE_CLIENT_WELCOME = "client_welcome"
TEMPLATE_CLIENT_ACTIVATION = "client_activation"
TEMPLATE_COMMITTEE_INVITE = "committee_invite"
TEMPLATE_ADMINISTRATOR_INVITE = "administrator_invite"
TEMPLATE_CARETAKER_INVITE = "caretaker_invite"
TEMPLATE_RESIDENT_INVITE = "resident_invite"

EMAIL_TEMPLATE_KEYS = (
    TEMPLATE_CLIENT_WELCOME,
    TEMPLATE_CLIENT_ACTIVATION,
    TEMPLATE_COMMITTEE_INVITE,
    TEMPLATE_ADMINISTRATOR_INVITE,
    TEMPLATE_CARETAKER_INVITE,
    TEMPLATE_RESIDENT_INVITE,
)

ROLE_TO_TEMPLATE = {
    "client": TEMPLATE_CLIENT_WELCOME,
    "committee": TEMPLATE_COMMITTEE_INVITE,
    "administrator": TEMPLATE_ADMINISTRATOR_INVITE,
    "caretaker": TEMPLATE_CARETAKER_INVITE,
    "resident": TEMPLATE_RESIDENT_INVITE,
}


@dataclass(frozen=True)
class EmailTemplateRecord:
    """One editable email template stored for the platform."""

    id: str
    key: str
    name: str
    subject: str
    html_body: str
    updated_at: str


class EmailTemplateNotFound(Exception):
    """Raised when a template key or id does not exist."""
