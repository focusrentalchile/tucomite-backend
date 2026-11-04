"""Persistence for management periods."""

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.periods import PERIOD_STATUS_CLOSED, PERIOD_STATUS_OPEN, PeriodRecord
from app.models.periods import PeriodModel


class PeriodRepository(Protocol):
    """Persistence port used by the period service."""

    def list_periods(self, client_id: str) -> list[PeriodRecord]:
        """Return periods for one building ordered by name."""

    def get_period(self, period_id: str) -> PeriodRecord | None:
        """Return one period when present."""

    def get_open_period(self, client_id: str) -> PeriodRecord | None:
        """Return the open period for one building when one exists."""

    def create_period(self, period: PeriodRecord) -> PeriodRecord:
        """Insert one period."""

    def set_status(self, period_id: str, status: str) -> PeriodRecord:
        """Update the status of one period."""

    def close_all_open(self, client_id: str) -> None:
        """Mark every open period for one building as closed."""

    def claim_legacy_open(self, client_id: str) -> PeriodRecord | None:
        """Attach a legacy global open period (no client) to this building once."""

    def assign_client(self, period_id: str, client_id: str) -> PeriodRecord:
        """Set client_id on a legacy period row."""


class SqlPeriodRepository:
    """SQLAlchemy adapter for the periods table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_periods(self, client_id: str) -> list[PeriodRecord]:
        rows = self._session.execute(
            select(PeriodModel)
            .where(PeriodModel.client_id == client_id)
            .order_by(PeriodModel.name),
        ).scalars().all()
        return [self._record(row) for row in rows]

    def get_period(self, period_id: str) -> PeriodRecord | None:
        row = self._session.get(PeriodModel, period_id)
        if row is None:
            return None
        return self._record(row)

    def get_open_period(self, client_id: str) -> PeriodRecord | None:
        row = self._session.execute(
            select(PeriodModel).where(
                PeriodModel.status == PERIOD_STATUS_OPEN,
                PeriodModel.client_id == client_id,
            ),
        ).scalars().first()
        if row is None:
            return None
        return self._record(row)

    def create_period(self, period: PeriodRecord) -> PeriodRecord:
        self._session.add(
            PeriodModel(
                id=period.id,
                name=period.name,
                status=period.status,
                client_id=period.client_id,
            ),
        )
        self._session.flush()
        return period

    def set_status(self, period_id: str, status: str) -> PeriodRecord:
        row = self._session.get(PeriodModel, period_id)
        if row is None:
            raise LookupError(period_id)
        row.status = status
        self._session.flush()
        return self._record(row)

    def close_all_open(self, client_id: str) -> None:
        rows = self._session.execute(
            select(PeriodModel).where(
                PeriodModel.status == PERIOD_STATUS_OPEN,
                PeriodModel.client_id == client_id,
            ),
        ).scalars().all()
        for row in rows:
            row.status = PERIOD_STATUS_CLOSED
        self._session.flush()

    def claim_legacy_open(self, client_id: str) -> PeriodRecord | None:
        """Give this building ownership of one legacy open period with no client_id."""
        row = self._session.execute(
            select(PeriodModel).where(
                PeriodModel.status == PERIOD_STATUS_OPEN,
                PeriodModel.client_id.is_(None),
            ),
        ).scalars().first()
        if row is None:
            return None
        row.client_id = client_id
        self._session.flush()
        return self._record(row)

    def assign_client(self, period_id: str, client_id: str) -> PeriodRecord:
        row = self._session.get(PeriodModel, period_id)
        if row is None:
            raise LookupError(period_id)
        row.client_id = client_id
        self._session.flush()
        return self._record(row)

    def _record(self, row: PeriodModel) -> PeriodRecord:
        return PeriodRecord(
            id=row.id,
            name=row.name,
            status=row.status,
            client_id=getattr(row, "client_id", None),
        )
