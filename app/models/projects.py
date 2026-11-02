"""MySQL tables for building projects and their attachments."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProjectModel(Base):
    """A project managed by the committee inside one period."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    period_id: Mapped[str] = mapped_column(String(36), ForeignKey("periods.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    photo_names: Mapped[str] = mapped_column(String(1000), default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectAttachmentModel(Base):
    """One image, video, or file attached to a project (url may be a data URL)."""

    __tablename__ = "project_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(MEDIUMTEXT().with_variant(Text(), "sqlite"))
