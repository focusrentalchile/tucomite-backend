"""Unit tests for Gestión assignment in-app notices."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.management import MANAGEMENT_STATUS_TODO, ManagementTaskRecord
from app.domain.notifications import NotificationRecord
from app.services.management_service import ManagementService


@dataclass
class _FakeNotifications:
    items: list[NotificationRecord] = field(default_factory=list)

    def add(self, record: NotificationRecord) -> NotificationRecord:
        self.items.append(record)
        return record


class _FakeManagementRepo:
    def __init__(self) -> None:
        self.task: ManagementTaskRecord | None = None

    def add_task(self, ticket: ManagementTaskRecord) -> None:
        self.task = ticket

    def get_task(self, task_id: str) -> ManagementTaskRecord | None:
        if self.task is None or self.task.id != task_id:
            return None
        return self.task


def test_create_task_notifies_assignee() -> None:
    repo = _FakeManagementRepo()
    notices = _FakeNotifications()
    service = ManagementService(repo, notifications=notices)  # type: ignore[arg-type]
    created = service.create_task(
        subject="Cámaras patio",
        body="Instalar cobertura.",
        created_by_user_id="committee-1",
        created_by_name="Comité",
        client_id="client-1",
        client_name="Edificio Norte",
        from_staff=False,
        assignee_user_id="admin-1",
        topic_id="topic-1",
    )
    assert created.status == MANAGEMENT_STATUS_TODO
    assert len(notices.items) == 1
    notice = notices.items[0]
    assert notice.user_id == "admin-1"
    assert notice.kind == "management_task_assigned"
    assert "Cámaras patio" in notice.body
