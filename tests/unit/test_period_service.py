"""Unit tests for opening management periods."""

from app.domain.periods import PERIOD_STATUS_CLOSED, PERIOD_STATUS_OPEN
from app.services.period_service import PeriodService
from tests.support.memory_period_repository import InMemoryPeriodRepository


def test_open_period_closes_the_previous_open_period() -> None:
    service = PeriodService(InMemoryPeriodRepository())

    first = service.open_period("2025")
    assert first.status == PERIOD_STATUS_OPEN
    assert service.get_open_period() == first

    second = service.open_period("2026")
    assert second.status == PERIOD_STATUS_OPEN
    assert service.get_open_period() == second
    listed = {period.name: period.status for period in service.list_periods()}
    assert listed["2025"] == PERIOD_STATUS_CLOSED
    assert listed["2026"] == PERIOD_STATUS_OPEN
