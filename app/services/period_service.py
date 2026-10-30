"""Open and list management periods."""

from datetime import date
from uuid import uuid4

from app.domain.periods import PERIOD_STATUS_CLOSED, PERIOD_STATUS_OPEN, NoOpenPeriod, PeriodNotFound, PeriodRecord
from app.repositories.period_repository import PeriodRepository


def current_month_period_name(today: date | None = None) -> str:
    """Return the calendar-month period key (`YYYY-MM`)."""
    day = today or date.today()
    return f"{day.year}-{day.month:02d}"


class PeriodService:
    """Application rules for periods."""

    def __init__(self, repository: PeriodRepository) -> None:
        self._repository = repository

    def list_periods(self) -> list[PeriodRecord]:
        """Ensure the current month is open, then return every period."""
        self.ensure_current_month_open()
        return self._repository.list_periods()

    def get_open_period(self) -> PeriodRecord | None:
        """Return the open period without advancing the calendar."""
        return self._repository.get_open_period()

    def ensure_current_month_open(self, today: date | None = None) -> PeriodRecord:
        """Close a stale open period and open the calendar month if needed."""
        name = current_month_period_name(today)
        open_one = self._repository.get_open_period()
        if open_one is not None and open_one.name == name:
            return open_one
        existing = next((item for item in self._repository.list_periods() if item.name == name), None)
        self._repository.close_all_open()
        if existing is not None:
            return self._repository.set_status(existing.id, PERIOD_STATUS_OPEN)
        return self._repository.create_period(
            PeriodRecord(id=str(uuid4()), name=name, status=PERIOD_STATUS_OPEN),
        )

    def open_period(self, name: str) -> PeriodRecord:
        """Close any open period and open a new one with the given name."""
        self._repository.close_all_open()
        existing = next(
            (item for item in self._repository.list_periods() if item.name == name.strip()),
            None,
        )
        if existing is not None:
            return self._repository.set_status(existing.id, PERIOD_STATUS_OPEN)
        return self._repository.create_period(
            PeriodRecord(id=str(uuid4()), name=name.strip(), status=PERIOD_STATUS_OPEN),
        )

    def close_period(self, period_id: str) -> PeriodRecord:
        """Close one open period."""
        period = self._repository.get_period(period_id)
        if period is None:
            raise PeriodNotFound(period_id)
        if period.status != PERIOD_STATUS_OPEN:
            raise NoOpenPeriod(period_id)
        return self._repository.set_status(period_id, PERIOD_STATUS_CLOSED)
