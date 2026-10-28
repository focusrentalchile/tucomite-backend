"""Building management periods that must be opened before projects."""

from dataclasses import dataclass

PERIOD_STATUS_OPEN = "open"
PERIOD_STATUS_CLOSED = "closed"


@dataclass(frozen=True)
class PeriodRecord:
    """A management period with open or closed status."""

    id: str
    name: str
    status: str


class PeriodNotFound(Exception):
    """Raised when a period id does not exist."""


class PeriodAlreadyOpen(Exception):
    """Raised when trying to open while another open period exists and the rule forbids it."""


class NoOpenPeriod(Exception):
    """Raised when a project needs an open period and none exists."""
