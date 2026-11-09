"""MySQL singleton for platform-wide runtime settings."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlatformSettingsModel(Base):
    """One-row table for editable platform configuration (SMTP, public URL)."""

    __tablename__ = "platform_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    smtp_user: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_password: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_from: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    public_site_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
