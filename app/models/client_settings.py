"""MySQL table for per-building settings."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.domain.client_settings import (
    DEFAULT_VOTE_WINDOW_HIGH_HOURS,
    DEFAULT_VOTE_WINDOW_LOW_HOURS,
    DEFAULT_VOTE_WINDOW_MEDIUM_HOURS,
)


class ClientSettingsModel(Base):
    """One row per building with its default voting windows (hours) by topic priority."""

    __tablename__ = "client_settings"

    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), primary_key=True)
    vote_window_high_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_VOTE_WINDOW_HIGH_HOURS,
    )
    vote_window_medium_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_VOTE_WINDOW_MEDIUM_HOURS,
    )
    vote_window_low_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_VOTE_WINDOW_LOW_HOURS,
    )
