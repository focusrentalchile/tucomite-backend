"""Use cases for platform management tasks and Gestión workspace imports."""

import uuid
from datetime import datetime, timezone

from app.domain.management import (
    ALLOWED_MANAGEMENT_STATUSES,
    BuildingAdministratorRecord,
    IMPORT_STATUS_APPROVED,
    IMPORT_STATUS_PENDING,
    IMPORT_STATUS_REJECTED,
    IMPORT_STATUS_REVOKED,
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
from app.repositories.agreement_repository import AgreementRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.management_repository import ManagementRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.period_repository import PeriodRepository

AGREEMENT_CONTEXT_PERIODS = 6


class ManagementService:
    """Creates management tasks and workspace import requests."""

    def __init__(
        self,
        repository: ManagementRepository,
        *,
        clients: ClientRepository | None = None,
        access: AccessRepository | None = None,
        notifications: NotificationRepository | None = None,
        agreements: AgreementRepository | None = None,
        periods: PeriodRepository | None = None,
    ) -> None:
        self._repository = repository
        self._clients = clients
        self._access = access
        self._notifications = notifications
        self._agreements = agreements
        self._periods = periods

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

    def list_building_administrators(self, client_id: str) -> list[BuildingAdministratorRecord]:
        """Home administrators plus import history (pending, active, revoked, rejected)."""
        items: list[BuildingAdministratorRecord] = []
        home_ids: set[str] = set()
        if self._access is not None:
            roles = {role.id: role for role in self._access.list_roles()}
            for user in self._access.list_users():
                if user.client_id != client_id:
                    continue
                role = roles.get(user.role_id)
                if role is None or role.name != "administrator":
                    continue
                home_ids.add(user.id)
                items.append(
                    BuildingAdministratorRecord(
                        user_id=user.id,
                        full_name=user.full_name,
                        email=user.email,
                        home=True,
                        import_id=None,
                        status=IMPORT_STATUS_APPROVED,
                        created_at="",
                        resolved_at=None,
                    ),
                )
        listed_external: set[str] = set()
        for record in self._repository.list_imports_for_client(client_id):
            if record.administrator_user_id in home_ids and record.status == IMPORT_STATUS_APPROVED:
                continue
            if record.administrator_user_id in listed_external:
                continue
            listed_external.add(record.administrator_user_id)
            items.append(
                BuildingAdministratorRecord(
                    user_id=record.administrator_user_id,
                    full_name=record.administrator_name,
                    email=record.administrator_email,
                    home=False,
                    import_id=record.id,
                    status=record.status,
                    created_at=record.created_at,
                    resolved_at=record.resolved_at,
                ),
            )
        return items

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
        existing = self._repository.find_import_for_pair(administrator_user_id, client.id)
        now = datetime.now(timezone.utc).isoformat()
        if existing is not None:
            if existing.status == IMPORT_STATUS_APPROVED:
                raise ValueError("That building is already in your Gestión board.")
            if existing.status == IMPORT_STATUS_PENDING:
                raise ValueError("A permission request is already pending for that building.")
            # Re-enable the same history row when access was revoked or rejected.
            self._repository.save_import_status(existing.id, IMPORT_STATUS_PENDING, resolved_at=None)
            stored = self._repository.get_import(existing.id)
            if stored is None:
                raise TaskNotFound()
            self._notify_owner_of_import_request(
                owner_id=owner.id,
                administrator_user_id=administrator_user_id,
                client_name=client.name,
                stored=stored,
                now=now,
            )
            return stored
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
        self._notify_owner_of_import_request(
            owner_id=owner.id,
            administrator_user_id=administrator_user_id,
            client_name=client.name,
            stored=stored,
            now=now,
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
        if approve:
            self._notify_admin_of_approval(stored, client_name=client.name, now=now)
        return stored

    def revoke_import(
        self,
        import_id: str,
        *,
        owner_user_id: str,
    ) -> ManagementWorkspaceImportRecord:
        """Remove an approved Gestión grant so the administrator loses the building."""
        if self._clients is None:
            raise ValueError("Workspace imports are not available.")
        record = self._repository.get_import(import_id)
        if record is None:
            raise TaskNotFound()
        if record.status != IMPORT_STATUS_APPROVED:
            raise ValueError("Only an approved grant can be revoked.")
        client = self._clients.get_client(record.client_id)
        if client is None or client.admin_user_id != owner_user_id:
            raise PermissionError("Only the building owner can revoke this access.")
        now = datetime.now(timezone.utc).isoformat()
        self._repository.save_import_status(import_id, IMPORT_STATUS_REVOKED, resolved_at=now)
        stored = self._repository.get_import(import_id)
        if stored is None:
            raise TaskNotFound()
        return stored

    def _notify_owner_of_import_request(
        self,
        *,
        owner_id: str,
        administrator_user_id: str,
        client_name: str,
        stored: ManagementWorkspaceImportRecord,
        now: str,
    ) -> None:
        if self._notifications is None or self._access is None:
            return
        admin = self._access.get_user(administrator_user_id)
        admin_label = admin.full_name if admin is not None else stored.administrator_name
        admin_email = admin.email if admin is not None else stored.administrator_email
        self._notifications.add(
            NotificationRecord(
                id=str(uuid.uuid4()),
                user_id=owner_id,
                kind="management_import_request",
                title="Solicitud para gestionar tu edificio",
                body=(
                    f"El administrador {admin_label} ({admin_email}) quiere gestionar "
                    f"«{client_name}». Entrá a Administración para aprobar."
                ),
                created_at=now,
                read_at=None,
            ),
        )

    def _recent_agreement_titles(self, client_id: str) -> list[str]:
        """Agreement titles from the last six periods for onboarding context."""
        if self._agreements is None or self._periods is None:
            return []
        recent_period_ids = {
            period.id for period in self._periods.list_periods()[-AGREEMENT_CONTEXT_PERIODS:]
        }
        if not recent_period_ids:
            return [
                item.title
                for item in self._agreements.list_agreements(client_id=client_id)[:12]
            ]
        titles: list[str] = []
        for item in self._agreements.list_agreements(client_id=client_id):
            if item.period_id and item.period_id not in recent_period_ids:
                continue
            titles.append(item.title)
            if len(titles) >= 12:
                break
        return titles

    def _notify_admin_of_approval(
        self,
        stored: ManagementWorkspaceImportRecord,
        *,
        client_name: str,
        now: str,
    ) -> None:
        if self._notifications is None:
            return
        titles = self._recent_agreement_titles(stored.client_id)
        if titles:
            history = " · ".join(titles)
            body = (
                f"Ya podés gestionar «{client_name}» en Gestión y Acuerdos. "
                f"Historial de acuerdos (últimos 6 periodos): {history}."
            )
        else:
            body = (
                f"Ya podés gestionar «{client_name}» en Gestión y Acuerdos. "
                "Todavía no hay acuerdos en los últimos 6 periodos."
            )
        self._notifications.add(
            NotificationRecord(
                id=str(uuid.uuid4()),
                user_id=stored.administrator_user_id,
                kind="management_import_approved",
                title="Acceso aprobado al edificio",
                body=body,
                created_at=now,
                read_at=None,
            ),
        )

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

    def delete_task(self, task_id: str) -> None:
        """Remove a ticket and its messages."""
        self.get_task(task_id)
        self._repository.delete_task(task_id)
