"""Platform-wide editable settings (SMTP and public site URL)."""

from dataclasses import dataclass

PLATFORM_SETTINGS_ID = "platform"


@dataclass(frozen=True)
class PlatformSettingsRecord:
    """Stored SMTP and site URL values used by transactional email."""

    id: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_use_tls: bool
    public_site_url: str
