"""In-memory client settings repository for unit tests."""

from app.domain.client_settings import ClientSettingsRecord


class InMemoryClientSettingsRepository:
    """Stores building settings in a dict keyed by client id."""

    def __init__(self) -> None:
        self.rows: dict[str, ClientSettingsRecord] = {}

    def get(self, client_id: str) -> ClientSettingsRecord | None:
        return self.rows.get(client_id)

    def save(self, settings: ClientSettingsRecord) -> ClientSettingsRecord:
        self.rows[settings.client_id] = settings
        return settings
