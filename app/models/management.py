"""MySQL tables for platform management tasks."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domain.topics import MEDIUM_PRIORITY_ID


class ManagementTaskModel(Base):
    """One management task on the building board."""

    __tablename__ = "management_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    client_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="todo")
    priority_id: Mapped[int] = mapped_column(Integer, nullable=False, default=MEDIUM_PRIORITY_ID)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assignee_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    topic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ManagementMessageModel(Base):
    """One message posted on a management task."""

    __tablename__ = "management_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("management_tasks.id"), nullable=False, index=True)
    author_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    from_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ManagementWorkspaceImportModel(Base):
    """Permission request to add a building to an administrator's Gestión board."""

    __tablename__ = "management_workspace_imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    administrator_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
