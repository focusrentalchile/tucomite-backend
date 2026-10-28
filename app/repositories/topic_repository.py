"""Persistence for topic statuses, topics, and votes."""
from datetime import date, datetime, timezone
from typing import Protocol
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.domain.topics import CLOSED_STATUS_ID, StatusRecord, TopicRecord, TopicVoteRecord
from app.models.topics import StatusModel, TopicModel, TopicVoteModel

class TopicRepository(Protocol):
    """Persistence port used by the topic service."""
    def list_statuses(self) -> list[StatusRecord]:
        """Return every status in id order."""
    def add_status(self, status: StatusRecord) -> None:
        """Insert one status."""
    def save_status(self, status: StatusRecord) -> None:
        """Update the key stored for one status id."""
    def add_topic(self, topic: TopicRecord) -> None:
        """Insert one topic."""
    def get_topic(self, topic_id: str) -> TopicRecord | None:
        """Return one topic by id."""
    def save_topic_status(self, topic_id: str, status_id: int) -> None:
        """Update the board column for one topic."""
    def save_topic(self, topic: TopicRecord) -> None:
        """Update the editable fields for one topic."""
    def delete_topic(self, topic_id: str) -> None:
        """Remove one topic and its votes."""
    def list_topics(self) -> list[TopicRecord]:
        """Return every topic."""
    def list_votes(self, topic_id: str) -> list[TopicVoteRecord]:
        """Return every vote for one topic."""
    def list_votes_for_topics(self, topic_ids: list[str]) -> list[TopicVoteRecord]:
        """Return every vote belonging to the given topics."""
    def get_vote(self, topic_id: str, author_id: str) -> TopicVoteRecord | None:
        """Return the vote cast by one author on one topic."""
    def add_vote(self, vote: TopicVoteRecord) -> None:
        """Insert one vote."""
    def save_vote(self, vote: TopicVoteRecord) -> None:
        """Update the choice stored for one vote."""

class SqlTopicRepository:
    """SQLAlchemy adapter for the MySQL topic tables."""
    def __init__(self, session: Session) -> None:
        self._session = session
    def list_statuses(self) -> list[StatusRecord]:
        rows = self._session.scalars(select(StatusModel).order_by(StatusModel.id)).all()
        return [StatusRecord(id=row.id, key=row.key) for row in rows]
    def add_status(self, status: StatusRecord) -> None:
        self._session.add(StatusModel(id=status.id, key=status.key))
    def save_status(self, status: StatusRecord) -> None:
        row = self._session.get(StatusModel, status.id)
        if row is not None:
            row.key = status.key
    def add_topic(self, topic: TopicRecord) -> None:
        self._session.add(
            TopicModel(
                id=topic.id,
                title=topic.title,
                description=topic.description,
                category_key=topic.category_key,
                attachment_name=topic.attachment_name,
                decision=topic.decision,
                status_id=topic.status_id,
                priority_id=topic.priority_id,
                assignee_user_id=topic.assignee_user_id,
                due_date=date.fromisoformat(topic.due_date) if topic.due_date else None,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                closed_at=None,
                period_id=topic.period_id,
            ),
        )
    def get_topic(self, topic_id: str) -> TopicRecord | None:
        row = self._session.get(TopicModel, topic_id)
        if row is None:
            return None
        return self._topic(row)
    def save_topic_status(self, topic_id: str, status_id: int) -> None:
        row = self._session.get(TopicModel, topic_id)
        if row is not None:
            row.status_id = status_id
            if status_id == CLOSED_STATUS_ID:
                row.closed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            else:
                row.closed_at = None
    def save_topic(self, topic: TopicRecord) -> None:
        row = self._session.get(TopicModel, topic.id)
        if row is None:
            return
        row.title = topic.title
        row.description = topic.description
        row.category_key = topic.category_key
        row.attachment_name = topic.attachment_name
        row.decision = topic.decision
        row.status_id = topic.status_id
        row.priority_id = topic.priority_id
        row.assignee_user_id = topic.assignee_user_id
        row.due_date = date.fromisoformat(topic.due_date) if topic.due_date else None
        row.period_id = topic.period_id
    def save_topic_assignment(self, topic_id: str, assignee_user_id: str, due_date: str) -> None:
        """Store the person responsible and the completion date."""
        row = self._session.get(TopicModel, topic_id)
        if row is None:
            return
        row.assignee_user_id = assignee_user_id
        row.due_date = date.fromisoformat(due_date)
    def delete_topic(self, topic_id: str) -> None:
        votes = self._session.scalars(
            select(TopicVoteModel).where(TopicVoteModel.topic_id == topic_id),
        ).all()
        for vote in votes:
            self._session.delete(vote)
        row = self._session.get(TopicModel, topic_id)
        if row is not None:
            self._session.delete(row)
    def list_topics(self) -> list[TopicRecord]:
        rows = self._session.scalars(select(TopicModel).order_by(TopicModel.title)).all()
        return [self._topic(row) for row in rows]
    def list_votes(self, topic_id: str) -> list[TopicVoteRecord]:
        rows = self._session.scalars(
            select(TopicVoteModel)
            .where(TopicVoteModel.topic_id == topic_id)
            .order_by(TopicVoteModel.author_name),
        ).all()
        return [self._vote(row) for row in rows]
    def list_votes_for_topics(self, topic_ids: list[str]) -> list[TopicVoteRecord]:
        if not topic_ids:
            return []
        rows = self._session.scalars(
            select(TopicVoteModel)
            .where(TopicVoteModel.topic_id.in_(topic_ids))
            .order_by(TopicVoteModel.author_name),
        ).all()
        return [self._vote(row) for row in rows]
    def get_vote(self, topic_id: str, author_id: str) -> TopicVoteRecord | None:
        row = self._session.scalar(
            select(TopicVoteModel).where(
                TopicVoteModel.topic_id == topic_id,
                TopicVoteModel.author_id == author_id,
            ),
        )
        if row is None:
            return None
        return self._vote(row)
    def add_vote(self, vote: TopicVoteRecord) -> None:
        self._session.add(
            TopicVoteModel(
                id=vote.id,
                topic_id=vote.topic_id,
                author_id=vote.author_id,
                author_name=vote.author_name,
                choice=vote.choice,
            ),
        )
    def save_vote(self, vote: TopicVoteRecord) -> None:
        row = self._session.get(TopicVoteModel, vote.id)
        if row is not None:
            row.choice = vote.choice
            row.author_name = vote.author_name
    def _topic(self, row: TopicModel) -> TopicRecord:
        return TopicRecord(
            id=row.id,
            title=row.title,
            description=row.description,
            category_key=row.category_key,
            attachment_name=row.attachment_name,
            decision=row.decision,
            status_id=row.status_id,
            priority_id=row.priority_id,
            assignee_user_id=row.assignee_user_id,
            due_date=row.due_date.isoformat() if row.due_date else None,
            created_at=row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            closed_at=row.closed_at.isoformat() if getattr(row, "closed_at", None) else None,
            period_id=getattr(row, "period_id", None),
        )
    def _vote(self, row: TopicVoteModel) -> TopicVoteRecord:
        return TopicVoteRecord(
            id=row.id,
            topic_id=row.topic_id,
            author_id=row.author_id,
            author_name=row.author_name,
            choice=row.choice,
        )
