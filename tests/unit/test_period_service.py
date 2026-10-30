"""Unit tests for opening management periods."""

from datetime import date

from app.domain.periods import PERIOD_STATUS_CLOSED, PERIOD_STATUS_OPEN
from app.services.period_service import PeriodService, current_month_period_name
from tests.support.memory_period_repository import InMemoryPeriodRepository


def test_open_period_closes_the_previous_open_period() -> None:
    service = PeriodService(InMemoryPeriodRepository())

    first = service.open_period("2025-01")
    assert first.status == PERIOD_STATUS_OPEN
    assert service.get_open_period() == first

    second = service.open_period("2026-03")
    assert second.status == PERIOD_STATUS_OPEN
    assert service.get_open_period() == second
    listed = {period.name: period.status for period in service.list_periods()}
    assert listed["2025-01"] == PERIOD_STATUS_CLOSED
    # list_periods auto-opens the current calendar month
    assert listed[current_month_period_name()] == PERIOD_STATUS_OPEN


def test_close_period_marks_the_open_period_closed() -> None:
    service = PeriodService(InMemoryPeriodRepository())
    opened = service.open_period("2026-06")

    closed = service.close_period(opened.id)

    assert closed.status == PERIOD_STATUS_CLOSED
    assert service.get_open_period() is None


def test_ensure_current_month_open_advances_from_a_previous_month() -> None:
    service = PeriodService(InMemoryPeriodRepository())
    service.open_period("2024-01")

    opened = service.ensure_current_month_open(date(2026, 10, 15))

    assert opened.name == "2026-10"
    assert opened.status == PERIOD_STATUS_OPEN
    assert service.get_open_period() == opened
    listed = {period.name: period.status for period in service._repository.list_periods()}
    assert listed["2024-01"] == PERIOD_STATUS_CLOSED
