"""Seeds the status table, creates topics, and stores votes."""

import uuid
from dataclasses import replace
from datetime import datetime, timezone

from app.domain.topics import (
    ATTACHMENT_KINDS,
    CLOSED_STATUS_ID,
    DOING_STATUS_ID,
    MEDIUM_PRIORITY_ID,
    OPEN_STATUS_ID,
    PRIORITY_IDS,
    TOPIC_PRIORITIES,
    TOPIC_STATUSES,
    VOTE_CHOICES,
    VOTE_TYPE_CUSTOM,
    VOTE_TYPE_YES_NO,
    VOTE_TYPES,
    WAITING_STATUS_ID,
    CompletionAlreadySubmitted,
    CompletionNotSubmitted,
    CompletionQuorumNotMet,
    ConfirmationAlreadyCast,
    ExecutionQuorumNotMet,
    InvalidTopicPriority,
    InvalidTopicStatus,
    InvalidVoteChoice,
    InvalidVoteOptions,
    StatusRecord,
    TopicAttachmentRecord,
    COMPLETION_ROUND_FAILED,
    CONFIRMATION_CHOICES,
    CONFIRMATION_NO,
    CONFIRMATION_YES,
    TopicCompletionRoundRecord,
    TopicConfirmationRecord,
    TopicNotFound,
    TopicOpinionRecord,
    TopicRecord,
    TopicVoteOptionRecord,
    TopicVoteRecord,
    VoteAlreadyCast,
    completion_quorum_met,
    no_confirmation_count,
    yes_confirmation_count,
    ensure_voting_open,
    execution_quorum_met,
    resolve_voting_window,
)
from app.repositories.topic_repository import TopicRepository

_VALID_STATUS_IDS = {status_id for status_id, _ in TOPIC_STATUSES}


def ensure_topic_statuses(repository: TopicRepository) -> None:
    """Insert the four board statuses with their stable ids."""
    stored = {status.id: status for status in repository.list_statuses()}
    for status_id, key in TOPIC_STATUSES:
        current = stored.get(status_id)
        if current is None:
            repository.add_status(StatusRecord(id=status_id, key=key))
        elif current.key != key:
            repository.save_status(StatusRecord(id=status_id, key=key))


def ensure_topic_priorities(session) -> None:
    """Insert the three priority rows with their stable ids."""
    from app.models.topics import PriorityModel

    for priority_id, key in TOPIC_PRIORITIES:
        current = session.get(PriorityModel, priority_id)
        if current is None:
            session.add(PriorityModel(id=priority_id, key=key))
        elif current.key != key:
            current.key = key


def _winning_vote_count(topic: TopicRecord, votes: list[TopicVoteRecord]) -> int:
    """Yes tally for yes/no polls, or the leading custom option count."""
    if topic.vote_type == VOTE_TYPE_CUSTOM:
        if not topic.vote_options:
            return 0
        return max(
            (sum(1 for vote in votes if vote.choice == option.id) for option in topic.vote_options),
            default=0,
        )
    return sum(1 for vote in votes if vote.choice == "yes")


def _copy_topic(topic: TopicRecord, **changes) -> TopicRecord:
    """Return a TopicRecord with selected fields replaced."""
    return replace(topic, **changes)


def _normalize_vote_options(
    vote_type: str,
    options: list[dict[str, str]] | None,
) -> tuple[TopicVoteOptionRecord, ...]:
    """Build stored options. Custom polls need at least two labeled answers."""
    normalized_type = (vote_type or VOTE_TYPE_YES_NO).strip().lower()
    if normalized_type not in VOTE_TYPES:
        raise InvalidVoteOptions()
    if normalized_type != VOTE_TYPE_CUSTOM:
        return ()
    cleaned: list[TopicVoteOptionRecord] = []
    for item in options or []:
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        option_id = str(item.get("id") or "").strip() or str(uuid.uuid4())
        cleaned.append(TopicVoteOptionRecord(id=option_id, label=label[:120]))
    if len(cleaned) < 2:
        raise InvalidVoteOptions()
    return tuple(cleaned)


class TopicService:
    """Creates topics and records yes, no, or abstain votes in MySQL."""

    def __init__(self, repository: TopicRepository) -> None:
        self._repository = repository

    def list_topics(self) -> list[TopicRecord]:
        """Return every stored topic."""
        return self._repository.list_topics()

    def list_votes_for_topics(self, topic_ids: list[str]) -> list[TopicVoteRecord]:
        """Return every vote for the given topics."""
        return self._repository.list_votes_for_topics(topic_ids)

    def list_opinions_for_topics(self, topic_ids: list[str]) -> list[TopicOpinionRecord]:
        """Return every opinion for the given topics."""
        return self._repository.list_opinions_for_topics(topic_ids)

    def list_attachments_for_topics(self, topic_ids: list[str]) -> list[TopicAttachmentRecord]:
        """Return every attachment for the given topics."""
        return self._repository.list_attachments_for_topics(topic_ids)

    def list_completion_attachments_for_topics(
        self,
        topic_ids: list[str],
    ) -> list[TopicAttachmentRecord]:
        """Return completion evidence attachments for the given topics."""
        return self._repository.list_completion_attachments_for_topics(topic_ids)

    def list_confirmations_for_topics(self, topic_ids: list[str]) -> list[TopicConfirmationRecord]:
        """Return every completion confirmation for the given topics."""
        return self._repository.list_confirmations_for_topics(topic_ids)

    def _normalize_attachments(
        self,
        topic_id: str,
        attachments: list[dict[str, str]] | None,
    ) -> list[TopicAttachmentRecord]:
        stored: list[TopicAttachmentRecord] = []
        for item in attachments or []:
            kind = str(item.get("kind", "")).strip().lower()
            name = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
            if kind not in ATTACHMENT_KINDS or not name or not url:
                continue
            stored.append(
                TopicAttachmentRecord(
                    id=str(uuid.uuid4()),
                    topic_id=topic_id,
                    kind=kind,
                    name=name[:255],
                    url=url,
                ),
            )
        return stored

    def create_opinion(
        self,
        topic_id: str,
        author_id: str,
        author_name: str,
        body: str,
    ) -> TopicOpinionRecord:
        """Append a new opinion message on a topic."""
        topic = self._repository.get_topic(topic_id)
        if topic is None:
            raise TopicNotFound()
        text = body.strip()
        if not text:
            raise ValueError("Opinion body is required.")
        opinion = TopicOpinionRecord(
            id=str(uuid.uuid4()),
            topic_id=topic_id,
            author_id=author_id,
            author_name=author_name.strip(),
            body=text,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        )
        self._repository.add_opinion(opinion)
        return opinion

    def upsert_opinion(
        self,
        topic_id: str,
        author_id: str,
        author_name: str,
        body: str,
    ) -> TopicOpinionRecord:
        """Append a new opinion (legacy name kept for call sites)."""
        return self.create_opinion(topic_id, author_id, author_name, body)

    def delete_opinion(self, topic_id: str, opinion_id: str, author_id: str) -> None:
        """Remove one opinion when the actor wrote it."""
        topic = self._repository.get_topic(topic_id)
        if topic is None:
            raise TopicNotFound()
        opinion = self._repository.get_opinion_by_id(opinion_id)
        if opinion is None or opinion.topic_id != topic_id:
            raise TopicNotFound()
        if opinion.author_id != author_id:
            raise PermissionError("Only the author can delete this opinion.")
        self._repository.delete_opinion(opinion_id)

    def reassign_period(
        self,
        topic_id: str,
        period_id: str,
        client_id: str | None = None,
    ) -> TopicRecord:
        """Move one topic onto another period (used to recover stranded WIP topics).

        When the topic has no building yet, ``client_id`` stamps it so it stays visible
        to everyone in that building.
        """
        current = self._repository.get_topic(topic_id)
        if current is None:
            raise TopicNotFound()
        changes: dict = {"period_id": period_id}
        if client_id and not current.client_id:
            changes["client_id"] = client_id
        topic = _copy_topic(current, **changes)
        self._repository.save_topic(topic)
        return topic

    def create_topic(
        self,
        title: str,
        description: str,
        category_key: str,
        attachment_name: str,
        decision: str,
        priority_id: int = MEDIUM_PRIORITY_ID,
        period_id: str | None = None,
        attachments: list[dict[str, str]] | None = None,
        vote_type: str = VOTE_TYPE_YES_NO,
        vote_options: list[dict[str, str]] | None = None,
        client_id: str | None = None,
        voting_starts_at: str | None = None,
        voting_ends_at: str | None = None,
        default_window_hours: int | None = None,
    ) -> TopicRecord:
        """Store a topic in the open status.

        ``client_id`` is the creator's building, so everyone in it sees the topic.
        The voting window comes from the given dates; when no end is given and
        ``default_window_hours`` is set, the window closes that many hours after it opens.
        """
        if priority_id not in PRIORITY_IDS:
            raise InvalidTopicPriority()
        normalized_type = (vote_type or VOTE_TYPE_YES_NO).strip().lower()
        options = _normalize_vote_options(normalized_type, vote_options)
        window_starts, window_ends = resolve_voting_window(
            voting_starts_at,
            voting_ends_at,
            default_hours=default_window_hours,
        )
        topic = TopicRecord(
            id=str(uuid.uuid4()),
            title=title.strip(),
            description=description.strip(),
            category_key=category_key.strip(),
            attachment_name=attachment_name.strip(),
            decision=decision.strip(),
            status_id=OPEN_STATUS_ID,
            priority_id=priority_id,
            period_id=period_id,
            vote_type=normalized_type,
            vote_options=options,
            client_id=client_id,
            voting_starts_at=window_starts,
            voting_ends_at=window_ends,
        )
        self._repository.add_topic(topic)
        self._repository.replace_attachments(topic.id, self._normalize_attachments(topic.id, attachments))
        return topic

    def update_topic(
        self,
        topic_id: str,
        title: str,
        description: str,
        category_key: str,
        attachment_name: str,
        decision: str,
        priority_id: int = MEDIUM_PRIORITY_ID,
        attachments: list[dict[str, str]] | None = None,
        vote_type: str = VOTE_TYPE_YES_NO,
        vote_options: list[dict[str, str]] | None = None,
    ) -> TopicRecord:
        """Update the editable fields of one topic."""
        if priority_id not in PRIORITY_IDS:
            raise InvalidTopicPriority()
        current = self._repository.get_topic(topic_id)
        if current is None:
            raise TopicNotFound()
        normalized_type = (vote_type or VOTE_TYPE_YES_NO).strip().lower()
        options = _normalize_vote_options(normalized_type, vote_options)
        topic = _copy_topic(
            current,
            title=title.strip(),
            description=description.strip(),
            category_key=category_key.strip(),
            attachment_name=attachment_name.strip(),
            decision=decision.strip(),
            priority_id=priority_id,
            vote_type=normalized_type,
            vote_options=options,
        )
        self._repository.save_topic(topic)
        if attachments is not None:
            self._repository.replace_attachments(
                topic.id,
                self._normalize_attachments(topic.id, attachments),
            )
        return topic

    def move_topic(
        self,
        topic_id: str,
        status_id: int,
        *,
        committee_size: int | None = None,
    ) -> TopicRecord:
        """Move one topic to another board column."""
        if status_id not in _VALID_STATUS_IDS:
            raise InvalidTopicStatus()
        current = self._repository.get_topic(topic_id)
        if current is None:
            raise TopicNotFound()
        if status_id == CLOSED_STATUS_ID:
            if not current.completion_submitted_at:
                raise CompletionNotSubmitted()
            confirmations = self._repository.list_confirmations_for_topics([topic_id])
            size = committee_size if committee_size is not None else 0
            if not completion_quorum_met(yes_confirmation_count(confirmations), size):
                raise CompletionQuorumNotMet()
        if status_id == DOING_STATUS_ID:
            size = committee_size if committee_size is not None else 0
            votes = self._repository.list_votes_for_topics([topic_id])
            winning = _winning_vote_count(current, votes)
            if not execution_quorum_met(winning, size):
                raise ExecutionQuorumNotMet()
        self._repository.save_topic_status(topic_id, status_id)
        return _copy_topic(current, status_id=status_id)

    def submit_completion(
        self,
        topic_id: str,
        note: str,
        attachments: list[dict[str, str]] | None = None,
    ) -> TopicRecord:
        """Store the assignee solution note and evidence while in execution."""
        current = self._repository.get_topic(topic_id)
        if current is None:
            raise TopicNotFound()
        if current.status_id != DOING_STATUS_ID:
            raise InvalidTopicStatus()
        if current.completion_submitted_at:
            raise CompletionAlreadySubmitted()
        text = note.strip()
        if not text:
            raise ValueError("Completion note is required.")
        submitted_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        topic = _copy_topic(
            current,
            completion_note=text[:500],
            completion_submitted_at=submitted_at,
        )
        self._repository.save_topic_completion(topic)
        self._repository.replace_completion_attachments(
            topic.id,
            self._normalize_attachments(topic.id, attachments),
        )
        return topic

    def confirm_completion(
        self,
        topic_id: str,
        author_id: str,
        author_name: str,
        *,
        choice: str = CONFIRMATION_YES,
        reason: str | None = None,
        committee_size: int | None = None,
    ) -> tuple[TopicRecord, TopicConfirmationRecord]:
        """Record one committee Resultado vote (resolved yes/no).

        When No votes exceed 50% of the committee, seal Resultado N as failed,
        keep history, and clear the current culminación so a new attempt can load.
        """
        topic = self._repository.get_topic(topic_id)
        if topic is None:
            raise TopicNotFound()
        if topic.status_id != DOING_STATUS_ID:
            raise InvalidTopicStatus()
        if not topic.completion_submitted_at:
            raise CompletionNotSubmitted()
        existing = self._repository.get_confirmation(topic_id, author_id)
        if existing is not None:
            raise ConfirmationAlreadyCast()
        cleaned_choice = (choice or CONFIRMATION_YES).strip().casefold()
        if cleaned_choice not in CONFIRMATION_CHOICES:
            raise ValueError("Resultado choice must be yes or no.")
        cleaned_reason = (reason or "").strip()
        if cleaned_choice == CONFIRMATION_NO and not cleaned_reason:
            raise ValueError("A reason is required when voting no.")
        confirmation = TopicConfirmationRecord(
            id=str(uuid.uuid4()),
            topic_id=topic_id,
            author_id=author_id,
            author_name=author_name.strip(),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            choice=cleaned_choice,
            reason=cleaned_reason[:500] if cleaned_choice == CONFIRMATION_NO else None,
        )
        self._repository.add_confirmation(confirmation)
        confirmations = self._repository.list_confirmations_for_topics([topic_id])
        if not any(item.id == confirmation.id for item in confirmations):
            confirmations = [*confirmations, confirmation]
        size = committee_size if committee_size is not None else 0
        if size > 0 and no_confirmation_count(confirmations) > (size / 2):
            topic = self._fail_completion_round(topic, confirmations)
        return topic, confirmation

    def seal_failed_completion_if_needed(
        self,
        topic: TopicRecord,
        *,
        committee_size: int,
    ) -> TopicRecord:
        """If an open Resultado already has a No majority, seal it and reopen Culminación.

        Used when listing Gestión/Temas so stuck open deliveries heal after deploy.
        """
        if not topic.completion_submitted_at or committee_size <= 0:
            return topic
        confirmations = self._repository.list_confirmations_for_topics([topic.id])
        if no_confirmation_count(confirmations) > (committee_size / 2):
            return self._fail_completion_round(topic, confirmations)
        return topic

    def _fail_completion_round(
        self,
        topic: TopicRecord,
        confirmations: list[TopicConfirmationRecord],
    ) -> TopicRecord:
        """Archive the current Resultado as failed and reopen Culminación."""
        attachments = self._repository.list_completion_attachments_for_topics([topic.id])
        # History keeps names only; data-URL evidence would overflow topics.completion_rounds_json.
        compact_attachments = tuple(
            TopicAttachmentRecord(
                id=item.id,
                topic_id=item.topic_id,
                kind=item.kind,
                name=item.name,
                url="",
            )
            for item in attachments
        )
        closed_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        round_number = max(1, int(topic.completion_round or 1))
        sealed = TopicCompletionRoundRecord(
            round_number=round_number,
            note=(topic.completion_note or "").strip(),
            submitted_at=topic.completion_submitted_at or closed_at,
            closed_at=closed_at,
            outcome=COMPLETION_ROUND_FAILED,
            confirmations=tuple(confirmations),
            attachments=compact_attachments,
        )
        updated = _copy_topic(
            topic,
            completion_note=None,
            completion_submitted_at=None,
            completion_round=round_number + 1,
            completion_rounds=tuple([*topic.completion_rounds, sealed]),
        )
        self._repository.save_topic_completion(updated)
        self._repository.replace_completion_attachments(topic.id, [])
        self._repository.clear_confirmations_for_topic(topic.id)
        return updated

    def delete_topic(self, topic_id: str) -> None:
        """Remove one topic and its votes."""
        if self._repository.get_topic(topic_id) is None:
            raise TopicNotFound()
        self._repository.delete_topic(topic_id)

    def cast_vote(
        self,
        topic_id: str,
        author_id: str,
        author_name: str,
        choice: str,
        now: datetime | None = None,
    ) -> tuple[TopicRecord, TopicVoteRecord]:
        """Store one person's first vote and move the topic to waiting.

        Raises VotingWindowClosed when the topic has a voting window and ``now``
        (default: the current UTC time) is outside it.
        """
        topic = self._repository.get_topic(topic_id)
        if topic is None:
            raise TopicNotFound()
        ensure_voting_open(topic, now)
        normalized = choice.strip()
        allowed = (
            {option.id for option in topic.vote_options} | {"abstain"}
            if topic.vote_type == VOTE_TYPE_CUSTOM
            else VOTE_CHOICES
        )
        if topic.vote_type != VOTE_TYPE_CUSTOM:
            normalized = normalized.lower()
        if normalized not in allowed:
            raise InvalidVoteChoice()
        existing = self._repository.get_vote(topic_id, author_id)
        if existing is not None:
            # Voters may change their choice while the topic is still open or waiting.
            if topic.status_id not in {OPEN_STATUS_ID, WAITING_STATUS_ID}:
                raise VoteAlreadyCast()
            vote = TopicVoteRecord(
                id=existing.id,
                topic_id=topic_id,
                author_id=author_id,
                author_name=author_name.strip() or existing.author_name,
                choice=normalized,
            )
            self._repository.save_vote(vote)
            if topic.status_id == OPEN_STATUS_ID:
                self._repository.save_topic_status(topic_id, WAITING_STATUS_ID)
                topic = _copy_topic(topic, status_id=WAITING_STATUS_ID)
            return topic, vote
        vote = TopicVoteRecord(
            id=str(uuid.uuid4()),
            topic_id=topic_id,
            author_id=author_id,
            author_name=author_name.strip(),
            choice=normalized,
        )
        self._repository.add_vote(vote)
        if topic.status_id == OPEN_STATUS_ID:
            self._repository.save_topic_status(topic_id, WAITING_STATUS_ID)
            topic = _copy_topic(topic, status_id=WAITING_STATUS_ID)
        return topic, vote
