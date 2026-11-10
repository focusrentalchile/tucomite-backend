"""In-memory management repository for unit tests (tasks, messages, attachments)."""

from dataclasses import replace

from app.domain.management import (
    ManagementAttachmentRecord,
    ManagementMessageRecord,
    ManagementTaskRecord,
)


class InMemoryManagementRepository:
    """Stores tasks, their messages, and attachments without MySQL."""

    def __init__(self) -> None:
        self.tasks: dict[str, ManagementTaskRecord] = {}
        self.messages: list[ManagementMessageRecord] = []
        self.attachments: list[ManagementAttachmentRecord] = []

    def list_tasks(
        self,
        *,
        client_id: str | None = None,
        client_ids: list[str] | None = None,
    ) -> list[ManagementTaskRecord]:
        items = list(self.tasks.values())
        if client_ids is not None:
            items = [item for item in items if item.client_id in client_ids]
        elif client_id is not None:
            items = [item for item in items if item.client_id == client_id]
        return [replace(item, messages=(), attachments=()) for item in items]

    def get_task(self, task_id: str) -> ManagementTaskRecord | None:
        task = self.tasks.get(task_id)
        if task is None:
            return None
        messages = tuple(
            replace(
                message,
                attachments=tuple(item for item in self.attachments if item.message_id == message.id),
            )
            for message in self.messages
            if message.task_id == task_id
        )
        attachments = tuple(
            item for item in self.attachments if item.task_id == task_id and item.message_id is None
        )
        return replace(task, messages=messages, attachments=attachments)

    def add_task(self, ticket: ManagementTaskRecord) -> None:
        self.tasks[ticket.id] = replace(ticket, messages=(), attachments=())
        for message in ticket.messages:
            self.add_message(message)
        self.attachments.extend(ticket.attachments)

    def add_message(self, message: ManagementMessageRecord) -> None:
        self.messages.append(replace(message, attachments=()))
        self.attachments.extend(message.attachments)

    def save_task_status(self, task_id: str, status: str) -> None:
        self.tasks[task_id] = replace(self.tasks[task_id], status=status)

    def delete_task(self, task_id: str) -> None:
        self.tasks.pop(task_id)
        self.messages = [item for item in self.messages if item.task_id != task_id]
        self.attachments = [item for item in self.attachments if item.task_id != task_id]
