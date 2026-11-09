"""Unit tests for platform SMTP settings."""

from app.domain.platform_settings import PLATFORM_SETTINGS_ID, PlatformSettingsRecord
from app.services.platform_settings_service import PlatformSettingsService


class InMemoryPlatformSettingsRepository:
    def __init__(self) -> None:
        self.row: PlatformSettingsRecord | None = None

    def get(self) -> PlatformSettingsRecord | None:
        return self.row

    def save(self, settings: PlatformSettingsRecord) -> PlatformSettingsRecord:
        self.row = settings
        return settings


def test_update_keeps_password_when_blank() -> None:
    repo = InMemoryPlatformSettingsRepository()
    repo.row = PlatformSettingsRecord(
        id=PLATFORM_SETTINGS_ID,
        smtp_host="smtp.old.com",
        smtp_port=465,
        smtp_user="old",
        smtp_password="secret",
        smtp_from="old@tucomite.cl",
        smtp_use_tls=True,
        public_site_url="https://tucomite.cl",
    )
    service = PlatformSettingsService(repo)

    updated = service.update_settings(
        smtp_host="smtp.new.com",
        smtp_port=587,
        smtp_user="new",
        smtp_password="",
        smtp_from="new@tucomite.cl",
        smtp_use_tls=False,
        public_site_url="https://www.tucomite.cl",
    )

    assert updated.smtp_host == "smtp.new.com"
    assert updated.smtp_password == "secret"
    assert updated.smtp_use_tls is False
