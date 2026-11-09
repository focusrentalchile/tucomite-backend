"""Unit tests for opening management periods."""

from datetime import date

from app.domain.periods import PERIOD_STATUS_CLOSED, PERIOD_STATUS_OPEN
from app.services.period_service import PeriodService, current_month_period_name
from tests.support.memory_period_repository import InMemoryPeriodRepository

CLIENT_A = "client-a"
CLIENT_B = "client-b"


def test_open_period_closes_the_previous_open_period() -> None:
    service = PeriodService(InMemoryPeriodRepository())

    first = service.open_period(CLIENT_A, "2025-01")
    assert first.status == PERIOD_STATUS_OPEN
    assert service.get_open_period(CLIENT_A) == first

    second = service.open_period(CLIENT_A, "2026-03")
    assert second.status == PERIOD_STATUS_OPEN
    assert service.get_open_period(CLIENT_A) == second
    listed = {period.name: period.status for period in service.list_periods(CLIENT_A)}
    assert listed["2025-01"] == PERIOD_STATUS_CLOSED
    assert listed["2026-03"] == PERIOD_STATUS_OPEN
    assert current_month_period_name() not in listed or listed.get(current_month_period_name()) != PERIOD_STATUS_OPEN or current_month_period_name() == "2026-03"


def test_close_period_marks_the_open_period_closed() -> None:
    service = PeriodService(InMemoryPeriodRepository())
    opened = service.open_period(CLIENT_A, "2026-06")

    closed = service.close_period(CLIENT_A, opened.id)

    assert closed.status == PERIOD_STATUS_CLOSED
    assert service.get_open_period(CLIENT_A) is None


def test_ensure_keeps_existing_open_period_instead_of_advancing_month() -> None:
    service = PeriodService(InMemoryPeriodRepository())
    previous = service.open_period(CLIENT_A, "2024-01")

    opened = service.ensure_current_month_open(CLIENT_A, date(2026, 10, 15))

    assert opened.id == previous.id
    assert opened.name == "2024-01"
    assert opened.status == PERIOD_STATUS_OPEN
    assert service.get_open_period(CLIENT_A) == previous


def test_ensure_opens_calendar_month_when_nothing_is_open() -> None:
    service = PeriodService(InMemoryPeriodRepository())

    opened = service.ensure_current_month_open(CLIENT_A, date(2026, 10, 15))

    assert opened.name == "2026-10"
    assert opened.status == PERIOD_STATUS_OPEN
    assert service.get_open_period(CLIENT_A) == opened


def test_periods_are_isolated_per_client() -> None:
    service = PeriodService(InMemoryPeriodRepository())
    first = service.open_period(CLIENT_A, "2026-01")
    second = service.open_period(CLIENT_B, "2026-01")

    assert first.id != second.id
    assert service.get_open_period(CLIENT_A) == first
    assert service.get_open_period(CLIENT_B) == second
    assert len(service.list_periods(CLIENT_A)) >= 1
    assert all(period.client_id == CLIENT_A for period in service._repository.list_periods(CLIENT_A))
