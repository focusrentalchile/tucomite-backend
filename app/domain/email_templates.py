"""Domain records for editable transactional email templates."""

from dataclasses import dataclass

TEMPLATE_CLIENT_WELCOME = "client_welcome"
TEMPLATE_CLIENT_ACTIVATION = "client_activation"
TEMPLATE_PLATFORM_INVITE = "platform_invite"
TEMPLATE_COMMITTEE_INVITE = "committee_invite"
TEMPLATE_ADMINISTRATOR_INVITE = "administrator_invite"
TEMPLATE_CARETAKER_INVITE = "caretaker_invite"
TEMPLATE_RESIDENT_INVITE = "resident_invite"
TEMPLATE_TOPIC_CREATED = "topic_created"
TEMPLATE_TOPIC_STATUS_CHANGED = "topic_status_changed"
TEMPLATE_TOPIC_RESULTADO_VOTE = "topic_resultado_vote"
TEMPLATE_TOPIC_DELETED = "topic_deleted"
TEMPLATE_TOPIC_OPINION = "topic_opinion"
TEMPLATE_TOPIC_ASSIGN_READY = "topic_assign_ready"
TEMPLATE_MANAGEMENT_TASK_ASSIGNED = "management_task_assigned"
TEMPLATE_MANAGEMENT_TASK_STATUS_CHANGED = "management_task_status_changed"
TEMPLATE_MANAGEMENT_TASK_COMPLETION_REVIEW = "management_task_completion_review"

EMAIL_TEMPLATE_KEYS = (
    TEMPLATE_PLATFORM_INVITE,
    TEMPLATE_CLIENT_WELCOME,
    TEMPLATE_CLIENT_ACTIVATION,
    TEMPLATE_COMMITTEE_INVITE,
    TEMPLATE_ADMINISTRATOR_INVITE,
    TEMPLATE_CARETAKER_INVITE,
    TEMPLATE_RESIDENT_INVITE,
    TEMPLATE_TOPIC_CREATED,
    TEMPLATE_TOPIC_STATUS_CHANGED,
    TEMPLATE_TOPIC_RESULTADO_VOTE,
    TEMPLATE_TOPIC_DELETED,
    TEMPLATE_TOPIC_OPINION,
    TEMPLATE_TOPIC_ASSIGN_READY,
    TEMPLATE_MANAGEMENT_TASK_ASSIGNED,
    TEMPLATE_MANAGEMENT_TASK_STATUS_CHANGED,
    TEMPLATE_MANAGEMENT_TASK_COMPLETION_REVIEW,
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
