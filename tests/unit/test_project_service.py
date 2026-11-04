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
    open_period = period_service.open_period("client-1", "2026")
    service = ProjectService(InMemoryProjectRepository(), periods)

    created = service.create_project(
        open_period.id,
        "Jardin",
        "Arreglar el patio.",
        "patio.jpg",
        due_date="2026-04-01",
        attachments=[
            {"kind": "image", "name": "patio.jpg", "url": "data:image/png;base64,aaa"},
            {"kind": "file", "name": "plano.pdf", "url": "data:application/pdf;base64,bbb"},
        ],
    )
    assert created.period_id == open_period.id
    assert created.title == "Jardin"
    assert created.due_date == "2026-04-01"
    assert service.list_projects(open_period.id) == [created]
    assert len(service.list_attachments_for_projects([created.id])) == 2

    updated = service.update_project(
        created.id,
        "Jardín",
        "Arreglar el patio común.",
        "patio.jpg,macetas.png",
        due_date="2026-05-01",
        attachments=[{"kind": "image", "name": "macetas.png", "url": "data:image/png;base64,ccc"}],
    )
    assert updated.title == "Jardín"
    assert updated.due_date == "2026-05-01"
    assert service.list_projects(open_period.id) == [updated]
    assert len(service.list_attachments_for_projects([updated.id])) == 1

    service.delete_project(created.id)
    assert service.list_projects(open_period.id) == []


def test_create_requires_open_period() -> None:
    periods = InMemoryPeriodRepository()
    service = ProjectService(InMemoryProjectRepository(), periods)

    with pytest.raises(PeriodNotFound):
        service.create_project("missing", "Titulo", "Descripcion", "")

    closed = periods.create_period(
        PeriodRecord(id="p-closed", name="2024", status=PERIOD_STATUS_CLOSED, client_id="client-1"),
    )
    with pytest.raises(NoOpenPeriod):
        service.create_project(closed.id, "Titulo", "Descripcion", "")


def test_update_and_delete_missing_project_raise() -> None:
    service = ProjectService(InMemoryProjectRepository(), InMemoryPeriodRepository())

    with pytest.raises(ProjectNotFound):
        service.update_project("missing", "Titulo", "Descripcion", "")

    with pytest.raises(ProjectNotFound):
        service.delete_project("missing")
