"""Open and list management periods."""

from datetime import date
from uuid import uuid4

from app.domain.periods import PERIOD_STATUS_OPEN, NoOpenPeriod, PeriodNotFound, PeriodRecord
from app.repositories.period_repository import PeriodRepository


def current_month_period_name(today: date | None = None) -> str:
    """Return the calendar-month period key (`YYYY-MM`)."""
    day = today or date.today()
    return f"{day.year}-{day.month:02d}"


class PeriodService:
    """Application rules for periods. Every operation is scoped to one building."""

    def __init__(self, repository: PeriodRepository) -> None:
        self._repository = repository

    def list_periods(self, client_id: str) -> list[PeriodRecord]:
        """Ensure the current month is open for the building, then return its periods."""
        self.ensure_current_month_open(client_id)
        return self._repository.list_periods(client_id)

    def get_open_period(self, client_id: str) -> PeriodRecord | None:
        """Return the open period for one building without advancing the calendar."""
        return self._repository.get_open_period(client_id)

    def ensure_current_month_open(
        self,
        client_id: str,
        today: date | None = None,
    ) -> PeriodRecord:
        """Close a stale open period for this building and open the calendar month if needed."""
        name = current_month_period_name(today)
        open_one = self._repository.get_open_period(client_id)
        if open_one is None:
            claimed = self._repository.claim_legacy_open(client_id)
            if claimed is not None:
                open_one = claimed
        if open_one is not None and open_one.name == name:
            return open_one
        existing = next(
            (item for item in self._repository.list_periods(client_id) if item.name == name),
            None,
        )
        self._repository.close_all_open(client_id)
        if existing is not None:
            return self._repository.set_status(existing.id, PERIOD_STATUS_OPEN)
        return self._repository.create_period(
            PeriodRecord(
                id=str(uuid4()),
                name=name,
                status=PERIOD_STATUS_OPEN,
                client_id=client_id,
            ),
        )

    def open_period(self, client_id: str, name: str) -> PeriodRecord:
        """Close any open period for this building and open a new one with the given name."""
        self._repository.close_all_open(client_id)
        existing = next(
            (item for item in self._repository.list_periods(client_id) if item.name == name.strip()),
            None,
        )
        if existing is not None:
            return self._repository.set_status(existing.id, PERIOD_STATUS_OPEN)
        return self._repository.create_period(
            PeriodRecord(
                id=str(uuid4()),
                name=name.strip(),
                status=PERIOD_STATUS_OPEN,
                client_id=client_id,
            ),
        )

    def close_period(self, client_id: str, period_id: str) -> PeriodRecord:
        """Close one open period that belongs to this building."""
        period = self._repository.get_period(period_id)
        if period is None:
            raise PeriodNotFound(period_id)
        if period.client_id is None:
            period = self._repository.assign_client(period_id, client_id)
        elif period.client_id != client_id:
            raise PeriodNotFound(period_id)
        if period.status != PERIOD_STATUS_OPEN:
            raise NoOpenPeriod(period_id)
        return self._repository.set_status(period_id, PERIOD_STATUS_CLOSED)
