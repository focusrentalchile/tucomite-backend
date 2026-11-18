"""Topic board statuses and stored topic records."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# Stable ids shared with the admin board. 1 is the open column.
OPEN_STATUS_ID = 1
WAITING_STATUS_ID = 2
DOING_STATUS_ID = 3
CLOSED_STATUS_ID = 4

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
VOTE_TYPE_YES_NO = "yes_no"
VOTE_TYPE_CUSTOM = "custom"
VOTE_TYPES = frozenset({VOTE_TYPE_YES_NO, VOTE_TYPE_CUSTOM})
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
class TopicVoteOptionRecord:
    """One answer option for a custom poll."""

    id: str
    label: str


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
    start_date: str | None = None
    due_date: str | None = None
    created_at: str | None = None
    closed_at: str | None = None
    period_id: str | None = None
    completion_note: str | None = None
    completion_submitted_at: str | None = None
    # 1-based index of the open Resultado attempt.
    completion_round: int = 1
    # Sealed Resultado attempts (failed or passed) kept for history.
    completion_rounds: tuple["TopicCompletionRoundRecord", ...] = ()
    vote_type: str = VOTE_TYPE_YES_NO
    vote_options: tuple[TopicVoteOptionRecord, ...] = ()
    client_id: str | None = None
    # UTC ISO-8601 instants. None on either side means that side of the window is open.
    voting_starts_at: str | None = None
    voting_ends_at: str | None = None
    # When the committee was emailed that voting closed without a majority.
    no_consensus_notified_at: str | None = None
    # When the topic entered its current board column.
    status_entered_at: str | None = None
    # Soft delete (passive archive). Hidden from boards when set.
    deleted_at: str | None = None


@dataclass(frozen=True)
class TopicVoteRecord:
    """One person's vote: yes/no/abstain or a custom option id."""

    id: str
    topic_id: str
    author_id: str
    author_name: str
    choice: str


@dataclass(frozen=True)
class TopicOpinionRecord:
    """One written opinion message on a topic (authors may post many)."""

    id: str
    topic_id: str
    author_id: str
    author_name: str
    body: str
    created_at: str
    reply_to_opinion_id: str | None = None
    # Optional WhatsApp-style voice note (data URL) and duration in milliseconds.
    audio_url: str | None = None
    audio_duration_ms: int | None = None


CONFIRMATION_YES = "yes"
CONFIRMATION_NO = "no"
CONFIRMATION_CHOICES = frozenset({CONFIRMATION_YES, CONFIRMATION_NO})


@dataclass(frozen=True)
class TopicConfirmationRecord:
    """One committee Resultado vote: resolved yes/no (reason required for no)."""

    id: str
    topic_id: str
    author_id: str
    author_name: str
    created_at: str
    choice: str = CONFIRMATION_YES
    reason: str | None = None


COMPLETION_ROUND_FAILED = "failed"
COMPLETION_ROUND_PASSED = "passed"


ATTACHMENT_KINDS = frozenset({"image", "video", "file"})


@dataclass(frozen=True)
class TopicAttachmentRecord:
    """One stored image, video, or file preview for a topic."""

    id: str
    topic_id: str
    kind: str
    name: str
    url: str


@dataclass(frozen=True)
class TopicCompletionRoundRecord:
    """One sealed Resultado attempt kept after No majority or successful close."""

    round_number: int
    note: str
    submitted_at: str
    closed_at: str
    outcome: str
    confirmations: tuple[TopicConfirmationRecord, ...] = ()
    attachments: tuple[TopicAttachmentRecord, ...] = ()


def completion_quorum_met(confirmed_count: int, committee_size: int) -> bool:
    """True when strictly more than half the committee voted that it was resolved."""
    if committee_size <= 0:
        return False
    return confirmed_count > (committee_size / 2)


def yes_confirmation_count(confirmations: list[TopicConfirmationRecord]) -> int:
    """Count Resultado votes that say the topic was resolved."""
    return sum(
        1
        for item in confirmations
        if (item.choice or CONFIRMATION_YES).casefold() == CONFIRMATION_YES
    )


def no_confirmation_count(confirmations: list[TopicConfirmationRecord]) -> int:
    """Count Resultado votes that say the work did not culminate."""
    return sum(
        1
        for item in confirmations
        if (item.choice or "").casefold() == CONFIRMATION_NO
    )


def execution_quorum_met(winning_vote_count: int, committee_size: int) -> bool:
    """True when a vote option has a strict majority to assign execution."""
    return completion_quorum_met(winning_vote_count, committee_size)


def winning_vote_count(topic: "TopicRecord", votes: list["TopicVoteRecord"]) -> int:
    """Yes tally for yes/no polls, or the leading custom option count."""
    if topic.vote_type == VOTE_TYPE_CUSTOM:
        if not topic.vote_options:
            return 0
        return max(
            (sum(1 for vote in votes if vote.choice == option.id) for option in topic.vote_options),
            default=0,
        )
    return sum(1 for vote in votes if vote.choice == "yes")


def is_assign_ready(
    topic: "TopicRecord",
    votes: list["TopicVoteRecord"],
    committee_size: int,
) -> bool:
    """True when the topic waits for a responsible person and the vote majority is met."""
    if topic.status_id != WAITING_STATUS_ID or topic.assignee_user_id:
        return False
    return execution_quorum_met(winning_vote_count(topic, votes), committee_size)


class ExecutionQuorumNotMet(Exception):
    """Raised when assigning execution without a vote majority."""


class TopicNotFound(Exception):
    """Raised when a topic id does not exist."""


class InvalidVoteChoice(Exception):
    """Raised when a vote choice is not allowed for the topic poll type."""


class InvalidVoteOptions(Exception):
    """Raised when a custom poll does not include at least two options."""


class VoteAlreadyCast(Exception):
    """Raised when the person already voted on this topic."""


class ConfirmationAlreadyCast(Exception):
    """Raised when the person already confirmed topic completion."""


class CompletionNotSubmitted(Exception):
    """Raised when completion evidence is required but missing."""


class CompletionAlreadySubmitted(Exception):
    """Raised when completion evidence was already submitted."""


class CompletionQuorumNotMet(Exception):
    """Raised when closing requires more than 50% committee confirmations."""


class InvalidTopicStatus(Exception):
    """Raised when a status id is not one of the board columns."""


class InvalidTopicPriority(Exception):
    """Raised when a priority id is not high, medium, or low."""


class InvalidVotingWindow(Exception):
    """Raised when a voting window is malformed or ends before it starts."""


class VotingWindowClosed(Exception):
    """Raised when a vote is cast outside the topic's voting window.

    ``reason`` is ``"not_started"`` before the window opens and ``"ended"`` after it closes.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def parse_instant(value: str | datetime | None) -> datetime | None:
    """Parse an ISO-8601 string into an aware UTC datetime. Naive values are read as UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as error:
            raise InvalidVotingWindow() from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_voting_window(
    starts_at: str | datetime | None,
    ends_at: str | datetime | None,
    *,
    default_hours: int | None = None,
    now: datetime | None = None,
) -> tuple[str | None, str | None]:
    """Return the stored (starts, ends) pair as UTC ISO strings.

    When ``ends_at`` is omitted and ``default_hours`` is given, the window closes that many
    hours after it opens (the opening defaults to ``now``).
    """
    moment = now or datetime.now(timezone.utc)
    start = parse_instant(starts_at)
    end = parse_instant(ends_at)
    if end is None and default_hours is not None:
        start = start or moment
        end = start + timedelta(hours=default_hours)
    if start is not None and end is not None and end <= start:
        raise InvalidVotingWindow()
    return (
        start.isoformat() if start is not None else None,
        end.isoformat() if end is not None else None,
    )


def is_voting_window_ended(topic: "TopicRecord", now: datetime | None = None) -> bool:
    """True when ``now`` is after the configured voting end."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    end = parse_instant(topic.voting_ends_at)
    return end is not None and moment > end


def all_voters_have_voted(
    votes: list["TopicVoteRecord"],
    committee_size: int,
) -> bool:
    """True when every committee seat already cast a vote (one vote per person)."""
    if committee_size <= 0:
        return False
    authors = {vote.author_id for vote in votes if vote.author_id}
    return len(authors) >= committee_size


def is_no_consensus(
    topic: "TopicRecord",
    votes: list["TopicVoteRecord"],
    committee_size: int,
    now: datetime | None = None,
    *,
    grace_days: int | None = None,
) -> bool:
    """Waiting topic without a vote majority that should show “sin consenso”.

    Triggers when:
    - every voter already cast a ballot and there is still no >50% winner, or
    - ``voting_ends_at`` already passed and there is still no >50% winner
      (missing votes count as failure to reach consensus).

    ``grace_days`` is ignored (kept for call-site compatibility).
    """
    _ = grace_days  # No longer used; voting_ends_at is the only deadline.
    if topic.status_id != WAITING_STATUS_ID or topic.assignee_user_id:
        return False
    if execution_quorum_met(winning_vote_count(topic, votes), committee_size):
        return False
    if all_voters_have_voted(votes, committee_size):
        return True
    return is_voting_window_ended(topic, now)


def ensure_voting_open(
    topic: "TopicRecord",
    now: datetime | None = None,
    *,
    votes: list["TopicVoteRecord"] | None = None,
    committee_size: int = 0,
    grace_days: int | None = None,
) -> None:
    """Raise VotingWindowClosed when voting has not started yet.

    Abiertos and Esperando decisión stay votable after ``voting_ends_at`` (and when
    there is still no majority), so the committee can keep casting or changing votes
    until execution is assigned. Doing/Closed topics reject late ballots.
    """
    _ = (votes, committee_size, grace_days)  # Kept for call-site compatibility.
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    start = parse_instant(topic.voting_starts_at)
    end = parse_instant(topic.voting_ends_at)
    if start is not None and moment < start:
        raise VotingWindowClosed("not_started")
    if end is not None and moment > end:
        if topic.status_id in {OPEN_STATUS_ID, WAITING_STATUS_ID}:
            return
        raise VotingWindowClosed("ended")
