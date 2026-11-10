"""MySQL tables for topic statuses, priorities, topics, and votes."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domain.topics import MEDIUM_PRIORITY_ID, OPEN_STATUS_ID


class StatusModel(Base):
    """A board column. Ids are stable: 1 open, 2 waiting, 3 doing, 4 closed."""

    __tablename__ = "statuses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    key: Mapped[str] = mapped_column(String(32), unique=True)


class PriorityModel(Base):
    """Topic priority. Ids are stable: 1 high, 2 medium, 3 low."""

    __tablename__ = "priorities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    key: Mapped[str] = mapped_column(String(32), unique=True)


class TopicModel(Base):
    """A topic. New rows start in the open status."""

    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(500))
    category_key: Mapped[str] = mapped_column(String(64))
    attachment_name: Mapped[str] = mapped_column(String(255), default="")
    decision: Mapped[str] = mapped_column(String(500))
    vote_type: Mapped[str] = mapped_column(String(16), default="yes_no")
    vote_options_json: Mapped[str] = mapped_column(Text, default="[]")
    status_id: Mapped[int] = mapped_column(ForeignKey("statuses.id"), default=OPEN_STATUS_ID)
    priority_id: Mapped[int] = mapped_column(ForeignKey("priorities.id"), default=MEDIUM_PRIORITY_ID)
    assignee_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("periods.id"), nullable=True, index=True)
    completion_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    completion_submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    voting_starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    voting_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TopicVoteModel(Base):
    """One vote per person. Choice is yes/no/abstain or a custom option id."""

    __tablename__ = "topic_votes"
    __table_args__ = (UniqueConstraint("topic_id", "author_id", name="uq_topic_votes_author"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)
    author_id: Mapped[str] = mapped_column(String(36), index=True)
    author_name: Mapped[str] = mapped_column(String(160))
    choice: Mapped[str] = mapped_column(String(36))


class TopicOpinionModel(Base):
    """One written opinion per person on a topic."""

    __tablename__ = "topic_opinions"
    __table_args__ = (UniqueConstraint("topic_id", "author_id", name="uq_topic_opinions_author"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)
    author_id: Mapped[str] = mapped_column(String(36), index=True)
    author_name: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class TopicConfirmationModel(Base):
    """One committee confirmation that execution work is finished."""

    __tablename__ = "topic_confirmations"
    __table_args__ = (UniqueConstraint("topic_id", "author_id", name="uq_topic_confirmations_author"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)
    author_id: Mapped[str] = mapped_column(String(36), index=True)
    author_name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class TopicAttachmentModel(Base):
    """One image, video, or file attached to a topic (url may be a data URL)."""

    __tablename__ = "topic_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(MEDIUMTEXT().with_variant(Text(), "sqlite"))


class TopicCompletionAttachmentModel(Base):
    """Evidence files uploaded when execution work is marked complete."""

    __tablename__ = "topic_completion_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(MEDIUMTEXT().with_variant(Text(), "sqlite"))
