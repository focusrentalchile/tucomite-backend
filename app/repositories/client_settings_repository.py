"""Persistence for per-building settings."""

from typing import Protocol

from sqlalchemy.orm import Session

from app.domain.client_settings import ClientSettingsRecord
from app.models.client_settings import ClientSettingsModel


class ClientSettingsRepository(Protocol):
    """Persistence port used by the client settings service."""

    def get(self, client_id: str) -> ClientSettingsRecord | None:
        """Return the stored settings of one building, or None."""

    def save(self, settings: ClientSettingsRecord) -> ClientSettingsRecord:
        """Insert or update the settings of one building."""


class SqlClientSettingsRepository:
    """SQLAlchemy adapter for the client_settings table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, client_id: str) -> ClientSettingsRecord | None:
        row = self._session.get(ClientSettingsModel, client_id)
        if row is None:
            return None
        return self._record(row)

    def save(self, settings: ClientSettingsRecord) -> ClientSettingsRecord:
        row = self._session.get(ClientSettingsModel, settings.client_id)
        if row is None:
            row = ClientSettingsModel(client_id=settings.client_id)
            self._session.add(row)
        row.vote_window_high_hours = settings.vote_window_high_hours
        row.vote_window_medium_hours = settings.vote_window_medium_hours
        row.vote_window_low_hours = settings.vote_window_low_hours
        self._session.flush()
        return self._record(row)

    def _record(self, row: ClientSettingsModel) -> ClientSettingsRecord:
        return ClientSettingsRecord(
            client_id=row.client_id,
            vote_window_high_hours=row.vote_window_high_hours,
            vote_window_medium_hours=row.vote_window_medium_hours,
            vote_window_low_hours=row.vote_window_low_hours,
        )
