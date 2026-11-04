"""In-memory period repository for unit tests."""

from app.domain.periods import PERIOD_STATUS_CLOSED, PERIOD_STATUS_OPEN, PeriodRecord


class InMemoryPeriodRepository:
    """Stores periods in a dict keyed by id."""

    def __init__(self) -> None:
        self._periods: dict[str, PeriodRecord] = {}

    def list_periods(self, client_id: str) -> list[PeriodRecord]:
        return sorted(
            (period for period in self._periods.values() if period.client_id == client_id),
            key=lambda period: period.name,
        )

    def get_period(self, period_id: str) -> PeriodRecord | None:
        return self._periods.get(period_id)

    def get_open_period(self, client_id: str) -> PeriodRecord | None:
        return next(
            (
                period
                for period in self._periods.values()
                if period.status == PERIOD_STATUS_OPEN and period.client_id == client_id
            ),
            None,
        )

    def create_period(self, period: PeriodRecord) -> PeriodRecord:
        self._periods[period.id] = period
        return period

    def set_status(self, period_id: str, status: str) -> PeriodRecord:
        current = self._periods[period_id]
        updated = PeriodRecord(
            id=current.id,
            name=current.name,
            status=status,
            client_id=current.client_id,
        )
        self._periods[period_id] = updated
        return updated

    def close_all_open(self, client_id: str) -> None:
        for period_id, period in list(self._periods.items()):
            if period.status == PERIOD_STATUS_OPEN and period.client_id == client_id:
                self._periods[period_id] = PeriodRecord(
                    id=period.id,
                    name=period.name,
                    status=PERIOD_STATUS_CLOSED,
                    client_id=period.client_id,
                )

    def claim_legacy_open(self, client_id: str) -> PeriodRecord | None:
        legacy = next(
            (
                period
                for period in self._periods.values()
                if period.status == PERIOD_STATUS_OPEN and period.client_id is None
            ),
            None,
        )
        if legacy is None:
            return None
        return self.assign_client(legacy.id, client_id)

    def assign_client(self, period_id: str, client_id: str) -> PeriodRecord:
        current = self._periods[period_id]
        updated = PeriodRecord(
            id=current.id,
            name=current.name,
            status=current.status,
            client_id=client_id,
        )
        self._periods[period_id] = updated
        return updated
