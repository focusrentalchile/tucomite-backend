"""MySQL tables for topic statuses, priorities, topics, and votes."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
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
    status_id: Mapped[int] = mapped_column(ForeignKey("statuses.id"), default=OPEN_STATUS_ID)
    priority_id: Mapped[int] = mapped_column(ForeignKey("priorities.id"), default=MEDIUM_PRIORITY_ID)


class TopicVoteModel(Base):
    """One vote per person on a topic. Choice is yes, no, or abstain."""

    __tablename__ = "topic_votes"
    __table_args__ = (UniqueConstraint("topic_id", "author_id", name="uq_topic_votes_author"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)
    author_id: Mapped[str] = mapped_column(String(36), index=True)
    author_name: Mapped[str] = mapped_column(String(160))
    choice: Mapped[str] = mapped_column(String(8))
