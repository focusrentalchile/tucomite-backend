"""Per-building settings, starting with the default voting window by topic priority."""

from dataclasses import dataclass

# Defaults: high 24 h, medium 72 h, low 168 h (one week).
DEFAULT_VOTE_WINDOW_HIGH_HOURS = 24
DEFAULT_VOTE_WINDOW_MEDIUM_HOURS = 72
DEFAULT_VOTE_WINDOW_LOW_HOURS = 168
MIN_VOTE_WINDOW_HOURS = 1
MAX_VOTE_WINDOW_HOURS = 24 * 365


@dataclass(frozen=True)
class ClientSettingsRecord:
    """Editable settings of one building."""

    client_id: str
    vote_window_high_hours: int = DEFAULT_VOTE_WINDOW_HIGH_HOURS
    vote_window_medium_hours: int = DEFAULT_VOTE_WINDOW_MEDIUM_HOURS
    vote_window_low_hours: int = DEFAULT_VOTE_WINDOW_LOW_HOURS

    def hours_for_priority(self, priority_id: int) -> int:
        """Return the default vote window length for a priority id (1 high, 2 medium, 3 low)."""
        if priority_id == 1:
            return self.vote_window_high_hours
        if priority_id == 3:
            return self.vote_window_low_hours
        return self.vote_window_medium_hours


class InvalidVoteWindowSettings(Exception):
    """Raised when a default vote window is outside the allowed range."""
