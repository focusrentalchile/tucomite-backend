"""Read and update the settings of one building (default voting windows)."""

from app.domain.client_settings import (
    MAX_CONSENSUS_GRACE_DAYS,
    MAX_VOTE_WINDOW_HOURS,
    MIN_CONSENSUS_GRACE_DAYS,
    MIN_VOTE_WINDOW_HOURS,
    ClientSettingsRecord,
    InvalidVoteWindowSettings,
)
from app.repositories.client_settings_repository import ClientSettingsRepository


class ClientSettingsService:
    """Returns stored settings or the defaults, and validates updates."""

    def __init__(self, repository: ClientSettingsRepository) -> None:
        self._repository = repository

    def get_settings(self, client_id: str) -> ClientSettingsRecord:
        """Return the building's settings, or the defaults when none were saved."""
        return self._repository.get(client_id) or ClientSettingsRecord(client_id=client_id)

    def hours_for_priority(self, client_id: str, priority_id: int) -> int:
        """Return the default vote window length (hours) for a topic priority."""
        return self.get_settings(client_id).hours_for_priority(priority_id)

    def consensus_grace_days(self, client_id: str) -> int:
        """Return how many days the committee may debate after a vote without majority."""
        return self.get_settings(client_id).consensus_grace_days

    def update_vote_window(
        self,
        client_id: str,
        *,
        high_hours: int,
        medium_hours: int,
        low_hours: int,
        consensus_grace_days: int,
    ) -> ClientSettingsRecord:
        """Save vote-window hours and consensus grace days for the building."""
        for hours in (high_hours, medium_hours, low_hours):
            if not MIN_VOTE_WINDOW_HOURS <= hours <= MAX_VOTE_WINDOW_HOURS:
                raise InvalidVoteWindowSettings()
        if not MIN_CONSENSUS_GRACE_DAYS <= consensus_grace_days <= MAX_CONSENSUS_GRACE_DAYS:
            raise InvalidVoteWindowSettings()
        return self._repository.save(
            ClientSettingsRecord(
                client_id=client_id,
                vote_window_high_hours=high_hours,
                vote_window_medium_hours=medium_hours,
                vote_window_low_hours=low_hours,
                consensus_grace_days=consensus_grace_days,
            ),
        )
