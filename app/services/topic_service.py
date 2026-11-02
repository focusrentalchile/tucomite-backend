"""Seeds the status table, creates topics, and stores votes."""

import uuid
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
    WAITING_STATUS_ID,
    CompletionAlreadySubmitted,
    CompletionNotSubmitted,
    CompletionQuorumNotMet,
    ConfirmationAlreadyCast,
    InvalidTopicPriority,
    InvalidTopicStatus,
    InvalidVoteChoice,
    StatusRecord,
    TopicAttachmentRecord,
    TopicConfirmationRecord,
    TopicNotFound,
    TopicOpinionRecord,
    TopicRecord,
    TopicVoteRecord,
    VoteAlreadyCast,
    completion_quorum_met,
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


def _copy_topic(topic: TopicRecord, **changes) -> TopicRecord:
    """Return a TopicRecord with selected fields replaced."""
    data = {
        "id": topic.id,
        "title": topic.title,
        "description": topic.description,
        "category_key": topic.category_key,
        "attachment_name": topic.attachment_name,
        "decision": topic.decision,
        "status_id": topic.status_id,
        "priority_id": topic.priority_id,
        "assignee_user_id": topic.assignee_user_id,
        "start_date": topic.start_date,
        "due_date": topic.due_date,
        "created_at": topic.created_at,
        "closed_at": topic.closed_at,
        "period_id": topic.period_id,
        "completion_note": topic.completion_note,
        "completion_submitted_at": topic.completion_submitted_at,
    }
    data.update(changes)
    return TopicRecord(**data)


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

    def upsert_opinion(
        self,
        topic_id: str,
        author_id: str,
        author_name: str,
        body: str,
    ) -> TopicOpinionRecord:
        """Create or replace one person's opinion on a topic."""
        topic = self._repository.get_topic(topic_id)
        if topic is None:
            raise TopicNotFound()
        text = body.strip()
        if not text:
            raise ValueError("Opinion body is required.")
        existing = self._repository.get_opinion(topic_id, author_id)
        if existing is not None:
            updated = TopicOpinionRecord(
                id=existing.id,
                topic_id=existing.topic_id,
                author_id=existing.author_id,
                author_name=author_name.strip(),
                body=text,
                created_at=existing.created_at,
            )
            self._repository.save_opinion(updated)
            return updated
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
    ) -> TopicRecord:
        """Store a topic in the open status."""
        if priority_id not in PRIORITY_IDS:
            raise InvalidTopicPriority()
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
    ) -> TopicRecord:
        """Update the editable fields of one topic."""
        if priority_id not in PRIORITY_IDS:
            raise InvalidTopicPriority()
        current = self._repository.get_topic(topic_id)
        if current is None:
            raise TopicNotFound()
        topic = _copy_topic(
            current,
            title=title.strip(),
            description=description.strip(),
            category_key=category_key.strip(),
            attachment_name=attachment_name.strip(),
            decision=decision.strip(),
            priority_id=priority_id,
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
            if not completion_quorum_met(len(confirmations), size):
                raise CompletionQuorumNotMet()
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
    ) -> tuple[TopicRecord, TopicConfirmationRecord]:
        """Record one committee confirmation that execution work is finished."""
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
        confirmation = TopicConfirmationRecord(
            id=str(uuid.uuid4()),
            topic_id=topic_id,
            author_id=author_id,
            author_name=author_name.strip(),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        )
        self._repository.add_confirmation(confirmation)
        return topic, confirmation

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
    ) -> tuple[TopicRecord, TopicVoteRecord]:
        """Store one person's first vote and move the topic to waiting."""
        normalized = choice.strip().lower()
        if normalized not in VOTE_CHOICES:
            raise InvalidVoteChoice()
        topic = self._repository.get_topic(topic_id)
        if topic is None:
            raise TopicNotFound()
        existing = self._repository.get_vote(topic_id, author_id)
        if existing is not None:
            raise VoteAlreadyCast()
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
