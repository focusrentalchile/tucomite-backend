"""Topic board statuses and stored topic records."""

from dataclasses import dataclass

# Stable ids shared with the admin board. 1 is the open column.
OPEN_STATUS_ID = 1
WAITING_STATUS_ID = 2
DOING_STATUS_ID = 3

TOPIC_STATUSES: tuple[tuple[int, str], ...] = (
    (1, "open"),
    (2, "waiting"),
    (3, "doing"),
    (4, "closed"),
)

# Stable ids for topic priority. 1 high, 2 medium, 3 low.
TOPIC_PRIORITIES: tuple[tuple[int, str], ...] = (
    (1, "high"),
    (2, "medium"),
    (3, "low"),
)
MEDIUM_PRIORITY_ID = 2

VOTE_CHOICES = frozenset({"yes", "no", "abstain"})
PRIORITY_IDS = frozenset(priority_id for priority_id, _ in TOPIC_PRIORITIES)


@dataclass(frozen=True)
class StatusRecord:
    """One row in the statuses table."""

    id: int
    key: str


@dataclass(frozen=True)
class PriorityRecord:
    """One row in the priorities table."""

    id: int
    key: str


@dataclass(frozen=True)
class TopicRecord:
    """A topic stored with its current status and priority."""

    id: str
    title: str
    description: str
    category_key: str
    attachment_name: str
    decision: str
    status_id: int
    priority_id: int
    assignee_user_id: str | None = None
    due_date: str | None = None


@dataclass(frozen=True)
class TopicVoteRecord:
    """One person's yes, no, or abstain on a topic decision."""

    id: str
    topic_id: str
    author_id: str
    author_name: str
    choice: str


class TopicNotFound(Exception):
    """Raised when a topic id does not exist."""


class InvalidVoteChoice(Exception):
    """Raised when a vote is not yes, no, or abstain."""


class VoteAlreadyCast(Exception):
    """Raised when the person already voted on this topic."""


class InvalidTopicStatus(Exception):
    """Raised when a status id is not one of the board columns."""


class InvalidTopicPriority(Exception):
    """Raised when a priority id is not high, medium, or low."""
