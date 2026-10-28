"""In-memory period repository for unit tests."""

from app.domain.periods import PERIOD_STATUS_CLOSED, PERIOD_STATUS_OPEN, PeriodRecord


class InMemoryPeriodRepository:
    """Stores periods in a dict keyed by id."""

    def __init__(self) -> None:
        self._periods: dict[str, PeriodRecord] = {}

    def list_periods(self) -> list[PeriodRecord]:
        return sorted(self._periods.values(), key=lambda period: period.name)

    def get_period(self, period_id: str) -> PeriodRecord | None:
        return self._periods.get(period_id)

    def get_open_period(self) -> PeriodRecord | None:
        return next((period for period in self._periods.values() if period.status == PERIOD_STATUS_OPEN), None)

    def create_period(self, period: PeriodRecord) -> PeriodRecord:
        self._periods[period.id] = period
        return period

    def set_status(self, period_id: str, status: str) -> PeriodRecord:
        current = self._periods[period_id]
        updated = PeriodRecord(id=current.id, name=current.name, status=status)
        self._periods[period_id] = updated
        return updated

    def close_all_open(self) -> None:
        for period_id, period in list(self._periods.items()):
            if period.status == PERIOD_STATUS_OPEN:
                self._periods[period_id] = PeriodRecord(
                    id=period.id,
                    name=period.name,
                    status=PERIOD_STATUS_CLOSED,
                )
