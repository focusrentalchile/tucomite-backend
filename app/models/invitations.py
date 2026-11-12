"""MySQL table for platform and building invitations."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InvitationModel(Base):
    """One invitation sent by a super admin or a building client."""

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="platform")
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    building_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    role_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    client_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    invited_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
