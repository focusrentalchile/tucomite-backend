"""Open and list management periods."""

from uuid import uuid4

from app.domain.periods import PERIOD_STATUS_OPEN, PeriodRecord
from app.repositories.period_repository import PeriodRepository


class PeriodService:
    """Application rules for periods."""

    def __init__(self, repository: PeriodRepository) -> None:
        self._repository = repository

    def list_periods(self) -> list[PeriodRecord]:
        """Return every period."""
        return self._repository.list_periods()

    def get_open_period(self) -> PeriodRecord | None:
        """Return the open period when present."""
        return self._repository.get_open_period()

    def open_period(self, name: str) -> PeriodRecord:
        """Close any open period and open a new one with the given name."""
        self._repository.close_all_open()
        return self._repository.create_period(
            PeriodRecord(id=str(uuid4()), name=name.strip(), status=PERIOD_STATUS_OPEN),
        )
