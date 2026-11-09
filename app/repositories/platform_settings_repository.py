"""Persistence for the platform settings singleton."""

from typing import Protocol

from sqlalchemy.orm import Session

from app.domain.platform_settings import PLATFORM_SETTINGS_ID, PlatformSettingsRecord
from app.models.platform_settings import PlatformSettingsModel


class PlatformSettingsRepository(Protocol):
    """Persistence port for platform settings."""

    def get(self) -> PlatformSettingsRecord | None:
        """Return the singleton row when present."""

    def save(self, settings: PlatformSettingsRecord) -> PlatformSettingsRecord:
        """Insert or update the singleton row."""


class SqlPlatformSettingsRepository:
    """SQLAlchemy adapter for platform_settings."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> PlatformSettingsRecord | None:
        row = self._session.get(PlatformSettingsModel, PLATFORM_SETTINGS_ID)
        if row is None:
            return None
        return self._record(row)

    def save(self, settings: PlatformSettingsRecord) -> PlatformSettingsRecord:
        row = self._session.get(PlatformSettingsModel, PLATFORM_SETTINGS_ID)
        if row is None:
            row = PlatformSettingsModel(id=PLATFORM_SETTINGS_ID)
            self._session.add(row)
        row.smtp_host = settings.smtp_host
        row.smtp_port = settings.smtp_port
        row.smtp_user = settings.smtp_user
        row.smtp_password = settings.smtp_password
        row.smtp_from = settings.smtp_from
        row.smtp_use_tls = settings.smtp_use_tls
        row.public_site_url = settings.public_site_url
        self._session.flush()
        return self._record(row)

    def _record(self, row: PlatformSettingsModel) -> PlatformSettingsRecord:
        return PlatformSettingsRecord(
            id=row.id,
            smtp_host=row.smtp_host or "",
            smtp_port=int(row.smtp_port or 587),
            smtp_user=row.smtp_user or "",
            smtp_password=row.smtp_password or "",
            smtp_from=row.smtp_from or "",
            smtp_use_tls=bool(row.smtp_use_tls),
            public_site_url=row.public_site_url or "",
        )
