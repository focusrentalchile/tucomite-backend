"""Unit tests for creating, updating, and deleting projects."""

import pytest

from app.domain.periods import PERIOD_STATUS_CLOSED, NoOpenPeriod, PeriodNotFound, PeriodRecord
from app.domain.projects import ProjectNotFound
from app.services.period_service import PeriodService
from app.services.project_service import ProjectService
from tests.support.memory_period_repository import InMemoryPeriodRepository
from tests.support.memory_project_repository import InMemoryProjectRepository


def test_create_list_update_and_delete_project() -> None:
    periods = InMemoryPeriodRepository()
    period_service = PeriodService(periods)
    open_period = period_service.open_period("2026")
    service = ProjectService(InMemoryProjectRepository(), periods)

    created = service.create_project(open_period.id, "Jardin", "Arreglar el patio.", "patio.jpg")
    assert created.period_id == open_period.id
    assert created.title == "Jardin"
    assert service.list_projects(open_period.id) == [created]

    updated = service.update_project(created.id, "Jardín", "Arreglar el patio común.", "patio.jpg,macetas.png")
    assert updated.title == "Jardín"
    assert service.list_projects(open_period.id) == [updated]

    service.delete_project(created.id)
    assert service.list_projects(open_period.id) == []


def test_create_requires_open_period() -> None:
    periods = InMemoryPeriodRepository()
    service = ProjectService(InMemoryProjectRepository(), periods)

    with pytest.raises(PeriodNotFound):
        service.create_project("missing", "Titulo", "Descripcion", "")

    closed = periods.create_period(PeriodRecord(id="p-closed", name="2024", status=PERIOD_STATUS_CLOSED))
    with pytest.raises(NoOpenPeriod):
        service.create_project(closed.id, "Titulo", "Descripcion", "")


def test_update_and_delete_missing_project_raise() -> None:
    service = ProjectService(InMemoryProjectRepository(), InMemoryPeriodRepository())

    with pytest.raises(ProjectNotFound):
        service.update_project("missing", "Titulo", "Descripcion", "")

    with pytest.raises(ProjectNotFound):
        service.delete_project("missing")
