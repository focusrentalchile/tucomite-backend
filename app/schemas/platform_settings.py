"""Schemas for platform SMTP settings."""

from pydantic import BaseModel, Field


class PlatformSettingsResponse(BaseModel):
    """SMTP settings returned to the admin UI (password never echoed)."""

    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_from: str
    smtp_use_tls: bool
    public_site_url: str
    password_set: bool


class UpdatePlatformSettingsRequest(BaseModel):
    """Editable SMTP fields. Omit or blank password to keep the current one."""

    smtp_host: str = Field(default="", max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = Field(default="", max_length=255)
    smtp_password: str | None = Field(default=None, max_length=255)
    smtp_from: str = Field(default="", max_length=255)
    smtp_use_tls: bool = True
    public_site_url: str = Field(default="", max_length=255)
