"""Persistence for management periods."""

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.periods import PERIOD_STATUS_CLOSED, PERIOD_STATUS_OPEN, PeriodRecord
from app.models.periods import PeriodModel


class PeriodRepository(Protocol):
    """Persistence port used by the period service."""

    def list_periods(self) -> list[PeriodRecord]:
        """Return every period ordered by name."""

    def get_period(self, period_id: str) -> PeriodRecord | None:
        """Return one period when present."""

    def get_open_period(self) -> PeriodRecord | None:
        """Return the open period when one exists."""

    def create_period(self, period: PeriodRecord) -> PeriodRecord:
        """Insert one period."""

    def set_status(self, period_id: str, status: str) -> PeriodRecord:
        """Update the status of one period."""

    def close_all_open(self) -> None:
        """Mark every open period as closed."""


class SqlPeriodRepository:
    """SQLAlchemy adapter for the periods table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_periods(self) -> list[PeriodRecord]:
        rows = self._session.execute(select(PeriodModel).order_by(PeriodModel.name)).scalars().all()
        return [self._record(row) for row in rows]

    def get_period(self, period_id: str) -> PeriodRecord | None:
        row = self._session.get(PeriodModel, period_id)
        if row is None:
            return None
        return self._record(row)

    def get_open_period(self) -> PeriodRecord | None:
        row = self._session.execute(
            select(PeriodModel).where(PeriodModel.status == PERIOD_STATUS_OPEN),
        ).scalars().first()
        if row is None:
            return None
        return self._record(row)

    def create_period(self, period: PeriodRecord) -> PeriodRecord:
        self._session.add(PeriodModel(id=period.id, name=period.name, status=period.status))
        self._session.flush()
        return period

    def set_status(self, period_id: str, status: str) -> PeriodRecord:
        row = self._session.get(PeriodModel, period_id)
        if row is None:
            raise LookupError(period_id)
        row.status = status
        self._session.flush()
        return self._record(row)

    def close_all_open(self) -> None:
        rows = self._session.execute(
            select(PeriodModel).where(PeriodModel.status == PERIOD_STATUS_OPEN),
        ).scalars().all()
        for row in rows:
            row.status = PERIOD_STATUS_CLOSED
        self._session.flush()

    def _record(self, row: PeriodModel) -> PeriodRecord:
        return PeriodRecord(id=row.id, name=row.name, status=row.status)
