"""MySQL table for published agreements and their PDF reports."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgreementModel(Base):
    """A closed topic published as an agreement with a PDF acta."""

    __tablename__ = "agreements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id"), unique=True, index=True)
    period_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    client_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    decision: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    category_key: Mapped[str] = mapped_column(String(64), default="")
    summary: Mapped[str] = mapped_column(MEDIUMTEXT().with_variant(Text(), "sqlite"))
    vote_yes: Mapped[int] = mapped_column(Integer, default=0)
    vote_no: Mapped[int] = mapped_column(Integer, default=0)
    vote_abstain: Mapped[int] = mapped_column(Integer, default=0)
    vote_result: Mapped[str] = mapped_column(String(32), default="no_votes")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    pdf_name: Mapped[str] = mapped_column(String(255), default="")
    pdf_bytes: Mapped[bytes] = mapped_column(LargeBinary)
