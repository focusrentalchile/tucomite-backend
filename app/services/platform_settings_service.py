"""Read and update platform SMTP settings for super admins."""

from app.core.config import settings as env_settings
from app.domain.platform_settings import PLATFORM_SETTINGS_ID, PlatformSettingsRecord
from app.repositories.platform_settings_repository import PlatformSettingsRepository


class PlatformSettingsService:
    """Merges DB overrides with environment defaults for email delivery."""

    def __init__(self, repository: PlatformSettingsRepository) -> None:
        self._repository = repository

    def get_settings(self) -> PlatformSettingsRecord:
        """Return stored settings, or env defaults when the row is missing."""
        stored = self._repository.get()
        if stored is not None:
            return stored
        return PlatformSettingsRecord(
            id=PLATFORM_SETTINGS_ID,
            smtp_host=env_settings.smtp_host,
            smtp_port=env_settings.smtp_port,
            smtp_user=env_settings.smtp_user,
            smtp_password=env_settings.smtp_password,
            smtp_from=env_settings.smtp_from,
            smtp_use_tls=env_settings.smtp_use_tls,
            public_site_url=env_settings.public_site_url,
        )

    def update_settings(
        self,
        *,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str | None,
        smtp_from: str,
        smtp_use_tls: bool,
        public_site_url: str,
    ) -> PlatformSettingsRecord:
        """Persist SMTP fields. Empty password keeps the previous secret."""
        current = self.get_settings()
        password = current.smtp_password
        if smtp_password is not None and smtp_password.strip() != "":
            password = smtp_password.strip()
        return self._repository.save(
            PlatformSettingsRecord(
                id=PLATFORM_SETTINGS_ID,
                smtp_host=smtp_host.strip(),
                smtp_port=smtp_port,
                smtp_user=smtp_user.strip(),
                smtp_password=password,
                smtp_from=smtp_from.strip(),
                smtp_use_tls=smtp_use_tls,
                public_site_url=public_site_url.strip(),
            ),
        )
