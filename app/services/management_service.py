"""Use cases for platform management tasks and Gestión workspace imports."""

import uuid
from datetime import datetime, timezone

from app.domain.management import (
    ALLOWED_MANAGEMENT_STATUSES,
    IMPORT_STATUS_APPROVED,
    IMPORT_STATUS_PENDING,
    IMPORT_STATUS_REJECTED,
    MANAGEMENT_STATUS_TODO,
    ManagementMessageRecord,
    ManagementTaskRecord,
    ManagementWorkspaceClientRecord,
    ManagementWorkspaceImportRecord,
    TaskNotFound,
)
from app.domain.notifications import NotificationRecord
from app.domain.topics import MEDIUM_PRIORITY_ID, PRIORITY_IDS
from app.repositories.access_repository import AccessRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.management_repository import ManagementRepository
from app.repositories.notification_repository import NotificationRepository


class ManagementService:
    """Creates management tasks and workspace import requests."""

    def __init__(
        self,
        repository: ManagementRepository,
        *,
        clients: ClientRepository | None = None,
        access: AccessRepository | None = None,
        notifications: NotificationRepository | None = None,
    ) -> None:
        self._repository = repository
        self._clients = clients
        self._access = access
        self._notifications = notifications

    def list_tasks(
        self,
        *,
        client_id: str | None = None,
        client_ids: list[str] | None = None,
    ) -> list[ManagementTaskRecord]:
        """Return tickets for one building, a workspace set, or every ticket."""
        return self._repository.list_tasks(client_id=client_id, client_ids=client_ids)

    def get_task(self, task_id: str) -> ManagementTaskRecord:
        """Return one ticket with messages."""
        task = self._repository.get_task(task_id)
        if task is None:
            raise TaskNotFound()
        return task

    def workspace_client_ids(self, *, user_id: str, home_client_id: str | None) -> list[str]:
        """Home building plus approved imports for this administrator."""
        ids: list[str] = []
        if home_client_id:
            ids.append(home_client_id)
        for client_id in self._repository.list_approved_client_ids(user_id):
            if client_id not in ids:
                ids.append(client_id)
        return ids

    def list_workspace_clients(
        self,
        *,
        user_id: str,
        home_client_id: str | None,
    ) -> list[ManagementWorkspaceClientRecord]:
        """Buildings the administrator may work on in Gestión."""
        if self._clients is None:
            return []
        items: list[ManagementWorkspaceClientRecord] = []
        for index, client_id in enumerate(self.workspace_client_ids(user_id=user_id, home_client_id=home_client_id)):
            client = self._clients.get_client(client_id)
            if client is None:
                continue
            items.append(
                ManagementWorkspaceClientRecord(
                    client_id=client.id,
                    client_name=client.name,
                    home=index == 0 and client_id == home_client_id,
                ),
            )
        return items

    def list_outgoing_imports(self, administrator_user_id: str) -> list[ManagementWorkspaceImportRecord]:
        """Import requests opened by this administrator."""
        return self._repository.list_imports_for_administrator(administrator_user_id)

    def list_incoming_imports(self, client_id: str) -> list[ManagementWorkspaceImportRecord]:
        """Pending import requests for a building owner to approve."""
        return self._repository.list_pending_imports_for_client(client_id)

    def request_import(
        self,
        *,
        administrator_user_id: str,
        home_client_id: str | None,
        owner_email: str,
    ) -> ManagementWorkspaceImportRecord:
        """Ask a building owner to allow this administrator into their Gestión board."""
        if self._access is None or self._clients is None:
            raise ValueError("Workspace imports are not available.")
        email = owner_email.strip().casefold()
        if not email:
            raise ValueError("Owner email is required.")
        owner = self._access.get_user_by_email(email)
        if owner is None:
            raise ValueError("No building owner matches that email.")
        client = None
        for item in self._clients.list_clients():
            if item.admin_user_id == owner.id:
                client = item
                break
        if client is None and owner.client_id:
            candidate = self._clients.get_client(owner.client_id)
            if candidate is not None and candidate.admin_user_id == owner.id:
                client = candidate
        if client is None:
            raise ValueError("That account is not a building owner.")
        if home_client_id and client.id == home_client_id:
            raise ValueError("That building is already your home client.")
        existing = self._repository.find_open_import(administrator_user_id, client.id)
        if existing is not None:
            if existing.status == IMPORT_STATUS_APPROVED:
                raise ValueError("That building is already in your Gestión board.")
            raise ValueError("A permission request is already pending for that building.")
        now = datetime.now(timezone.utc).isoformat()
        record = ManagementWorkspaceImportRecord(
            id=str(uuid.uuid4()),
            administrator_user_id=administrator_user_id,
            administrator_name="",
            administrator_email="",
            client_id=client.id,
            client_name=client.name,
            status=IMPORT_STATUS_PENDING,
            created_at=now,
            resolved_at=None,
        )
        self._repository.add_import(record)
        stored = self._repository.get_import(record.id)
        if stored is None:
            raise TaskNotFound()
        if self._notifications is not None and self._access is not None:
            admin = self._access.get_user(administrator_user_id)
            admin_label = admin.full_name if admin is not None else stored.administrator_name
            admin_email = admin.email if admin is not None else stored.administrator_email
            self._notifications.add(
                NotificationRecord(
                    id=str(uuid.uuid4()),
                    user_id=owner.id,
                    kind="management_import_request",
                    title="Solicitud para importar tu edificio",
                    body=(
                        f"El administrador {admin_label} ({admin_email}) quiere importar "
                        f"«{client.name}» a su tablero de Gestión. Entrá a Gestión para aprobar o rechazar."
                    ),
                    created_at=now,
                    read_at=None,
                ),
            )
        return stored

    def resolve_import(
        self,
        import_id: str,
        *,
        approve: bool,
        owner_user_id: str,
    ) -> ManagementWorkspaceImportRecord:
        """Approve or reject a pending import when the actor owns the building."""
        if self._clients is None:
            raise ValueError("Workspace imports are not available.")
        record = self._repository.get_import(import_id)
        if record is None:
            raise TaskNotFound()
        if record.status != IMPORT_STATUS_PENDING:
            raise ValueError("That request was already resolved.")
        client = self._clients.get_client(record.client_id)
        if client is None or client.admin_user_id != owner_user_id:
            raise PermissionError("Only the building owner can resolve this request.")
        status = IMPORT_STATUS_APPROVED if approve else IMPORT_STATUS_REJECTED
        now = datetime.now(timezone.utc).isoformat()
        self._repository.save_import_status(import_id, status, resolved_at=now)
        stored = self._repository.get_import(import_id)
        if stored is None:
            raise TaskNotFound()
        return stored

    def create_task(
        self,
        *,
        subject: str,
        body: str,
        created_by_user_id: str,
        created_by_name: str,
        client_id: str | None,
        client_name: str,
        from_staff: bool,
        priority_id: int = MEDIUM_PRIORITY_ID,
        due_date: str | None = None,
        assignee_user_id: str | None = None,
        topic_id: str | None = None,
    ) -> ManagementTaskRecord:
        """Open a ticket in the Tareas column with the first message."""
        cleaned_subject = subject.strip()
        cleaned_body = body.strip()
        if not cleaned_subject or not cleaned_body:
            raise ValueError("Subject and body are required.")
        if priority_id not in PRIORITY_IDS:
            raise ValueError("Unknown ticket priority.")
        now = datetime.now(timezone.utc).isoformat()
        task_id = str(uuid.uuid4())
        message = ManagementMessageRecord(
            id=str(uuid.uuid4()),
            task_id=task_id,
            author_user_id=created_by_user_id,
            author_name=created_by_name,
            body=cleaned_body,
            created_at=now,
            from_staff=from_staff,
        )
        ticket = ManagementTaskRecord(
            id=task_id,
            client_id=client_id,
            client_name=client_name,
            created_by_user_id=created_by_user_id,
            created_by_name=created_by_name,
            subject=cleaned_subject,
            status=MANAGEMENT_STATUS_TODO,
            priority_id=priority_id,
            due_date=due_date,
            assignee_user_id=assignee_user_id,
            topic_id=topic_id,
            created_at=now,
            updated_at=now,
            messages=(message,),
        )
        self._repository.add_task(ticket)
        return self.get_task(task_id)

    def add_message(
        self,
        task_id: str,
        *,
        body: str,
        author_user_id: str,
        author_name: str,
        from_staff: bool,
    ) -> ManagementTaskRecord:
        """Append a reply to an existing ticket."""
        task = self.get_task(task_id)
        cleaned_body = body.strip()
        if not cleaned_body:
            raise ValueError("Message body is required.")
        message = ManagementMessageRecord(
            id=str(uuid.uuid4()),
            task_id=task.id,
            author_user_id=author_user_id,
            author_name=author_name,
            body=cleaned_body,
            created_at=datetime.now(timezone.utc).isoformat(),
            from_staff=from_staff,
        )
        self._repository.add_message(message)
        if task.status == MANAGEMENT_STATUS_TODO and from_staff:
            self._repository.save_task_status(task.id, "in_progress")
        return self.get_task(task_id)

    def set_status(self, task_id: str, status: str) -> ManagementTaskRecord:
        """Change ticket board column when the value is allowed."""
        cleaned = status.strip().lower()
        if cleaned not in ALLOWED_MANAGEMENT_STATUSES:
            raise ValueError("Unknown ticket status.")
        self.get_task(task_id)
        self._repository.save_task_status(task_id, cleaned)
        return self.get_task(task_id)
