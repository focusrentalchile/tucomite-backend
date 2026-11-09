"""Open and list management periods."""

from datetime import date
from uuid import uuid4

from app.domain.periods import (
    PERIOD_STATUS_CLOSED,
    PERIOD_STATUS_OPEN,
    NoOpenPeriod,
    PeriodNotFound,
    PeriodRecord,
)
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
        """Return periods for the building. Opens the calendar month only when none is open."""
        if self._repository.get_open_period(client_id) is None:
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
        """Return the building's open period, or open the calendar month when none exists.

        Never replaces an already-open period. Auto-advancing the month was closing the
        active period on every Temas refresh and orphaning newly created topics.
        """
        open_one = self._repository.get_open_period(client_id)
        if open_one is None:
            claimed = self._repository.claim_legacy_open(client_id)
            if claimed is not None:
                return claimed
        if open_one is not None:
            return open_one

        name = current_month_period_name(today)
        existing = next(
            (item for item in self._repository.list_periods(client_id) if item.name == name),
            None,
        )
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
