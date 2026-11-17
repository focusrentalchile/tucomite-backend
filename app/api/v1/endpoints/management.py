"""Platform management task and Gestión workspace endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_current_actor, require_permission
from app.core.database import get_db
from app.domain.management import (
    MANAGEMENT_STATUS_DONE,
    MANAGEMENT_STATUS_IN_PROGRESS,
    MANAGEMENT_STATUS_TODO,
    TaskNotFound,
)
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.agreement_repository import SqlAgreementRepository
from app.repositories.client_repository import SqlClientRepository
from app.repositories.committee_repository import SqlCommitteeRepository
from app.repositories.management_repository import SqlManagementRepository
from app.repositories.notification_repository import SqlNotificationRepository
from app.repositories.period_repository import SqlPeriodRepository
from app.domain.topics import (
    CLOSED_STATUS_ID,
    CompletionAlreadySubmitted,
    InvalidTopicStatus,
    TopicNotFound,
)
from app.repositories.topic_repository import SqlTopicRepository
from app.schemas.management import (
    BuildingAdministratorListResponse,
    BuildingAdministratorResponse,
    CreateManagementMessageRequest,
    CreateManagementTaskRequest,
    CreateManagementWorkspaceImportRequest,
    ManagementAttachmentPayload,
    ManagementAttachmentResponse,
    ManagementMessageResponse,
    ManagementTaskListResponse,
    ManagementTaskResponse,
    ManagementWorkspaceClientListResponse,
    ManagementWorkspaceClientResponse,
    ManagementWorkspaceImportListResponse,
    ManagementWorkspaceImportResponse,
    UpdateManagementTaskStatusRequest,
)
from app.schemas.topics import (
    TopicAttachmentResponse,
    TopicCompletionRoundResponse,
    TopicConfirmationResponse,
)
from app.services.management_service import ManagementService
from app.services.management_task_status_notify import (
    notify_management_completion_for_review,
    notify_management_status_changed,
)
from app.services.topic_service import TopicService
from pydantic import BaseModel, Field

router = APIRouter(prefix="/management", tags=["management"])


def get_management_service(db: Session = Depends(get_db)) -> ManagementService:
    """Build a management service for the request."""
    return ManagementService(
        SqlManagementRepository(db),
        clients=SqlClientRepository(db),
        access=SqlAccessRepository(db),
        notifications=SqlNotificationRepository(db),
        agreements=SqlAgreementRepository(db),
        periods=SqlPeriodRepository(db),
    )


def _attachment_response(item) -> ManagementAttachmentResponse:
    return ManagementAttachmentResponse(
        id=item.id,
        kind=item.kind,
        name=item.name,
        url=item.url,
    )


def _message_response(message) -> ManagementMessageResponse:
    return ManagementMessageResponse(
        id=message.id,
        author_user_id=message.author_user_id,
        author_name=message.author_name,
        body=message.body,
        created_at=message.created_at,
        from_staff=message.from_staff,
        attachments=[_attachment_response(item) for item in message.attachments],
    )


def _confirmation_response(item) -> TopicConfirmationResponse:
    choice = (getattr(item, "choice", None) or "yes").casefold()
    return TopicConfirmationResponse(
        id=str(getattr(item, "id", "") or ""),
        author_id=str(getattr(item, "author_id", "") or ""),
        author_name=str(getattr(item, "author_name", "") or ""),
        created_at=str(getattr(item, "created_at", "") or ""),
        choice="no" if choice == "no" else "yes",
        reason=(str(item.reason) if getattr(item, "reason", None) else None),
    )


def _topic_attachment_response(item) -> TopicAttachmentResponse | None:
    kind = str(getattr(item, "kind", "") or "").casefold()
    if kind not in {"image", "video", "file"}:
        kind = "file"
    url = str(getattr(item, "url", "") or "")
    name = str(getattr(item, "name", "") or "")
    if not url or not name:
        return None
    return TopicAttachmentResponse(
        id=str(getattr(item, "id", "") or ""),
        kind=kind,  # type: ignore[arg-type]
        name=name,
        url=url,
    )


def _completion_round_response(item) -> TopicCompletionRoundResponse:
    outcome = getattr(item, "outcome", None)
    if outcome not in {"failed", "passed"}:
        outcome = "failed"
    attachments = []
    for file in getattr(item, "attachments", ()) or ():
        mapped = _topic_attachment_response(file)
        if mapped is not None:
            attachments.append(mapped)
    confirmations = []
    for vote in getattr(item, "confirmations", ()) or ():
        try:
            confirmations.append(_confirmation_response(vote))
        except Exception:
            continue
    return TopicCompletionRoundResponse(
        round_number=max(1, int(getattr(item, "round_number", 1) or 1)),
        note=str(getattr(item, "note", "") or ""),
        submitted_at=str(getattr(item, "submitted_at", "") or ""),
        closed_at=str(getattr(item, "closed_at", "") or ""),
        outcome=outcome,
        confirmations=confirmations,
        attachments=attachments,
    )


def _empty_completion_snapshot(topic) -> dict:
    return {
        "submitted_at": getattr(topic, "completion_submitted_at", None),
        "note": getattr(topic, "completion_note", None),
        "round": max(1, int(getattr(topic, "completion_round", 1) or 1)),
        "rounds": [],
        "confirmations": [],
    }


def _topic_completion_snapshot(
    db: Session,
    topic_ids: list[str],
    client_by_topic: dict[str, str] | None = None,
) -> dict[str, dict]:
    """Return topic_id → Resultado snapshot for Gestión fichas.

    Never raises: a bad linked topic must not break the whole Gestión board.
    """
    unique = [item for item in dict.fromkeys(topic_ids) if item]
    if not unique:
        return {}
    repo = SqlTopicRepository(db)
    topics = TopicService(repo)
    committee = SqlCommitteeRepository(db)
    seat_cache: dict[str, int] = {}
    clients = client_by_topic or {}
    out: dict[str, dict] = {}
    for topic_id in unique:
        try:
            topic = repo.get_topic(topic_id)
            if topic is None:
                continue
            client_id = topic.client_id or clients.get(topic_id) or ""
            if client_id not in seat_cache:
                try:
                    seat_cache[client_id] = (
                        committee.count_voter_seats(client_id) if client_id else 0
                    )
                except Exception:
                    seat_cache[client_id] = 0
            previous_status = topic.status_id
            try:
                topic = topics.seal_failed_completion_if_needed(
                    topic,
                    committee_size=seat_cache[client_id],
                )
            except Exception:
                # A failed heal must not poison the request transaction.
                try:
                    db.rollback()
                except Exception:
                    pass
                topic = repo.get_topic(topic_id) or topic
            else:
                if (
                    previous_status != CLOSED_STATUS_ID
                    and topic.status_id == CLOSED_STATUS_ID
                ):
                    # Keep CLOSED even if the PDF agreement fails.
                    try:
                        from app.api.v1.endpoints.topics import _publish_agreement_best_effort

                        _publish_agreement_best_effort(
                            db,
                            topic_id=topic.id,
                            client_id=client_id or None,
                        )
                    except Exception:
                        pass
            confirmations = []
            try:
                confirmations = [
                    _confirmation_response(item)
                    for item in repo.list_confirmations_for_topics([topic.id])
                ]
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                confirmations = []
            rounds = []
            for item in getattr(topic, "completion_rounds", ()) or ():
                try:
                    rounds.append(_completion_round_response(item))
                except Exception:
                    continue
            out[topic_id] = {
                "submitted_at": topic.completion_submitted_at,
                "note": topic.completion_note,
                "round": max(1, int(topic.completion_round or 1)),
                "rounds": rounds,
                "confirmations": confirmations,
            }
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            topic = None
            try:
                topic = repo.get_topic(topic_id)
            except Exception:
                topic = None
            if topic is not None:
                out[topic_id] = _empty_completion_snapshot(topic)
    return out


def _task_response(
    ticket,
    *,
    topic_completion_submitted_at: str | None = None,
    topic_completion_note: str | None = None,
    topic_completion_round: int = 1,
    topic_completion_rounds: list[TopicCompletionRoundResponse] | None = None,
    topic_confirmations: list[TopicConfirmationResponse] | None = None,
) -> ManagementTaskResponse:
    return ManagementTaskResponse(
        id=ticket.id,
        client_id=ticket.client_id,
        client_name=ticket.client_name,
        created_by_user_id=ticket.created_by_user_id,
        created_by_name=ticket.created_by_name,
        subject=ticket.subject,
        status=ticket.status,
        priority_id=ticket.priority_id,
        due_date=ticket.due_date,
        assignee_user_id=ticket.assignee_user_id,
        topic_id=ticket.topic_id,
        topic_completion_submitted_at=topic_completion_submitted_at,
        topic_completion_note=topic_completion_note,
        topic_completion_round=max(1, int(topic_completion_round or 1)),
        topic_completion_rounds=topic_completion_rounds or [],
        topic_confirmations=topic_confirmations or [],
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        status_entered_at=getattr(ticket, "status_entered_at", None) or ticket.created_at,
        messages=[_message_response(item) for item in ticket.messages],
        attachments=[_attachment_response(item) for item in ticket.attachments],
    )


def _task_response_from_snapshot(ticket, snapshot: dict | None) -> ManagementTaskResponse:
    data = snapshot or {}
    return _task_response(
        ticket,
        topic_completion_submitted_at=data.get("submitted_at"),
        topic_completion_note=data.get("note"),
        topic_completion_round=data.get("round", 1),
        topic_completion_rounds=data.get("rounds") or [],
        topic_confirmations=data.get("confirmations") or [],
    )


def _tasks_response(db: Session, tasks: list) -> list[ManagementTaskResponse]:
    topic_client: dict[str, str] = {}
    for item in tasks:
        topic_id = getattr(item, "topic_id", None)
        client_id = getattr(item, "client_id", None)
        if topic_id and client_id and topic_id not in topic_client:
            topic_client[topic_id] = client_id
    try:
        completion = _topic_completion_snapshot(
            db,
            [item.topic_id for item in tasks if getattr(item, "topic_id", None)],
            client_by_topic=topic_client,
        )
    except Exception:
        completion = {}
    items: list[ManagementTaskResponse] = []
    for item in tasks:
        try:
            items.append(
                _task_response_from_snapshot(
                    item,
                    completion.get(item.topic_id) if item.topic_id else None,
                ),
            )
        except Exception:
            items.append(_task_response(item))
    return items


def _import_response(record) -> ManagementWorkspaceImportResponse:
    return ManagementWorkspaceImportResponse(
        id=record.id,
        administrator_user_id=record.administrator_user_id,
        administrator_name=record.administrator_name,
        administrator_email=record.administrator_email,
        client_id=record.client_id,
        client_name=record.client_name,
        status=record.status,
        created_at=record.created_at,
        resolved_at=record.resolved_at,
    )


def _actor_name(db: Session, user_id: str) -> str:
    user = SqlAccessRepository(db).get_user(user_id)
    return user.full_name if user is not None else ""


def _client_name(db: Session, client_id: str | None) -> str:
    if not client_id:
        return ""
    client = SqlClientRepository(db).get_client(client_id)
    return client.name if client is not None else ""


def _owned_client_id(db: Session, actor: Actor) -> str | None:
    """Return the building id when the actor is that building's owner account."""
    clients = SqlClientRepository(db)
    for client in clients.list_clients():
        if client.admin_user_id == actor.user_id:
            return client.id
    if actor.client_id:
        client = clients.get_client(actor.client_id)
        if client is not None and client.admin_user_id == actor.user_id:
            return client.id
    return None


def _workspace_ids(service: ManagementService, actor: Actor) -> list[str] | None:
    """None means every building (super admin); otherwise the workspace set."""
    if actor.is_super_admin:
        return None
    return service.workspace_client_ids(user_id=actor.user_id, home_client_id=actor.client_id)


def _ensure_task_access(service: ManagementService, actor: Actor, task_client_id: str | None) -> None:
    if actor.is_super_admin:
        return
    allowed = _workspace_ids(service, actor) or []
    if not task_client_id or task_client_id not in allowed:
        raise HTTPException(status_code=404, detail="Ticket not found.")


@router.get("/workspace/clients", response_model=ManagementWorkspaceClientListResponse)
def list_workspace_clients(
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "view")),
) -> ManagementWorkspaceClientListResponse:
    """List buildings available on this administrator's Gestión board."""
    if actor.is_super_admin:
        return ManagementWorkspaceClientListResponse(items=[])
    items = service.list_workspace_clients(user_id=actor.user_id, home_client_id=actor.client_id)
    return ManagementWorkspaceClientListResponse(
        items=[
            ManagementWorkspaceClientResponse(
                client_id=item.client_id,
                client_name=item.client_name,
                home=item.home,
            )
            for item in items
        ],
    )


@router.get("/workspace/administrators", response_model=BuildingAdministratorListResponse)
def list_building_administrators(
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> BuildingAdministratorListResponse:
    """List administrators who manage the building owner's client."""
    if "management.approve_import" not in actor.permissions:
        raise HTTPException(status_code=403, detail="Forbidden.")
    owned = _owned_client_id(db, actor)
    if not owned:
        return BuildingAdministratorListResponse(items=[])
    items = service.list_building_administrators(owned)
    return BuildingAdministratorListResponse(
        items=[
            BuildingAdministratorResponse(
                user_id=item.user_id,
                full_name=item.full_name,
                email=item.email,
                home=item.home,
                import_id=item.import_id,
                status=item.status,
                created_at=item.created_at,
                resolved_at=item.resolved_at,
            )
            for item in items
        ],
    )


@router.get("/workspace/imports", response_model=ManagementWorkspaceImportListResponse)
def list_workspace_imports(
    scope: str = Query(default="outgoing"),
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> ManagementWorkspaceImportListResponse:
    """List outgoing requests (administrator) or incoming pending approvals (owner)."""
    cleaned = scope.strip().lower()
    if cleaned == "incoming":
        owned = _owned_client_id(db, actor)
        if not owned and "management.approve_import" not in actor.permissions:
            raise HTTPException(status_code=403, detail="Forbidden.")
        if not owned:
            return ManagementWorkspaceImportListResponse(items=[])
        items = service.list_incoming_imports(owned)
        return ManagementWorkspaceImportListResponse(items=[_import_response(item) for item in items])
    if "management.create" not in actor.permissions and "management.view" not in actor.permissions:
        raise HTTPException(status_code=403, detail="Forbidden.")
    items = service.list_outgoing_imports(actor.user_id)
    return ManagementWorkspaceImportListResponse(items=[_import_response(item) for item in items])


@router.post("/workspace/imports", response_model=ManagementWorkspaceImportResponse, status_code=201)
def create_workspace_import(
    body: CreateManagementWorkspaceImportRequest,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "create")),
) -> ManagementWorkspaceImportResponse:
    """Request permission to import another building into Gestión."""
    if actor.is_super_admin:
        raise HTTPException(status_code=403, detail="Staff does not import buildings into Gestión.")
    try:
        record = service.request_import(
            administrator_user_id=actor.user_id,
            home_client_id=actor.client_id,
            owner_email=body.owner_email,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _import_response(record)


@router.post("/workspace/imports/{import_id}/approve", response_model=ManagementWorkspaceImportResponse)
def approve_workspace_import(
    import_id: str,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(get_current_actor),
) -> ManagementWorkspaceImportResponse:
    """Building owner approves an administrator's Gestión import request."""
    try:
        record = service.resolve_import(import_id, approve=True, owner_user_id=actor.user_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Import request not found.") from None
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden.") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _import_response(record)


@router.post("/workspace/imports/{import_id}/reject", response_model=ManagementWorkspaceImportResponse)
def reject_workspace_import(
    import_id: str,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(get_current_actor),
) -> ManagementWorkspaceImportResponse:
    """Building owner rejects an administrator's Gestión import request."""
    try:
        record = service.resolve_import(import_id, approve=False, owner_user_id=actor.user_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Import request not found.") from None
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden.") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _import_response(record)


@router.post("/workspace/imports/{import_id}/revoke", response_model=ManagementWorkspaceImportResponse)
def revoke_workspace_import(
    import_id: str,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(get_current_actor),
) -> ManagementWorkspaceImportResponse:
    """Building owner revokes an approved Gestión grant."""
    if "management.approve_import" not in actor.permissions:
        raise HTTPException(status_code=403, detail="Forbidden.")
    try:
        record = service.revoke_import(import_id, owner_user_id=actor.user_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Import request not found.") from None
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden.") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _import_response(record)


@router.post("/workspace/imports/{import_id}/leave", response_model=ManagementWorkspaceImportResponse)
def leave_workspace_import(
    import_id: str,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "create")),
) -> ManagementWorkspaceImportResponse:
    """Administrator cancels a pending import or leaves an approved building."""
    if actor.is_super_admin:
        raise HTTPException(status_code=403, detail="Staff does not manage Gestión imports.")
    try:
        record = service.leave_import(import_id, administrator_user_id=actor.user_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Import request not found.") from None
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden.") from None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _import_response(record)


@router.get("/tasks", response_model=ManagementTaskListResponse)
def list_tasks(
    client_id: str | None = Query(default=None),
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "view")),
    db: Session = Depends(get_db),
) -> ManagementTaskListResponse:
    """List tasks for the actor's Gestión workspace, optionally filtered by client."""
    if actor.is_super_admin:
        tasks = service.list_tasks(client_id=client_id)
        return ManagementTaskListResponse(items=_tasks_response(db, tasks))
    allowed = _workspace_ids(service, actor) or []
    if not allowed:
        return ManagementTaskListResponse(items=[])
    if client_id:
        if client_id not in allowed:
            return ManagementTaskListResponse(items=[])
        tasks = service.list_tasks(client_id=client_id)
    else:
        tasks = service.list_tasks(client_ids=allowed)
    return ManagementTaskListResponse(items=_tasks_response(db, tasks))


@router.get("/tasks/{task_id}", response_model=ManagementTaskResponse)
def read_task(
    task_id: str,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "view")),
    db: Session = Depends(get_db),
) -> ManagementTaskResponse:
    """Return one ticket thread."""
    try:
        ticket = service.get_task(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    _ensure_task_access(service, actor, ticket.client_id)
    return _tasks_response(db, [ticket])[0]


@router.post("/tasks", response_model=ManagementTaskResponse, status_code=201)
def create_task(
    body: CreateManagementTaskRequest,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "create")),
    db: Session = Depends(get_db),
) -> ManagementTaskResponse:
    """Open a management task for a building in the actor's Gestión workspace."""
    if actor.is_super_admin:
        raise HTTPException(status_code=403, detail="Staff replies on existing tasks.")
    allowed = _workspace_ids(service, actor) or []
    target_client_id = body.client_id or actor.client_id
    if not target_client_id or target_client_id not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden.")
    try:
        ticket = service.create_task(
            subject=body.subject,
            body=body.body,
            created_by_user_id=actor.user_id,
            created_by_name=_actor_name(db, actor.user_id),
            client_id=target_client_id,
            client_name=_client_name(db, target_client_id),
            from_staff=False,
            priority_id=body.priority_id,
            due_date=body.due_date,
            attachments=[item.model_dump() for item in body.attachments],
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _task_response(ticket)


@router.post("/tasks/{task_id}/messages", response_model=ManagementTaskResponse, status_code=201)
def create_message(
    task_id: str,
    body: CreateManagementMessageRequest,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "reply")),
    db: Session = Depends(get_db),
) -> ManagementTaskResponse:
    """Add a reply to a ticket."""
    try:
        existing = service.get_task(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    _ensure_task_access(service, actor, existing.client_id)
    try:
        ticket = service.add_message(
            task_id,
            body=body.body,
            author_user_id=actor.user_id,
            author_name=_actor_name(db, actor.user_id),
            from_staff=actor.is_super_admin,
            attachments=[item.model_dump() for item in body.attachments],
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return _task_response(ticket)


class SubmitManagementCompletionRequest(BaseModel):
    """Administrator evidence for a topic-linked Gestión task."""

    note: str = Field(min_length=1, max_length=500)
    attachments: list[ManagementAttachmentPayload] = []


@router.patch("/tasks/{task_id}/status", response_model=ManagementTaskResponse)
def update_status(
    task_id: str,
    body: UpdateManagementTaskStatusRequest,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "reply")),
    db: Session = Depends(get_db),
) -> ManagementTaskResponse:
    """Move a ticket across Pendientes / En curso / Completadas."""
    try:
        existing = service.get_task(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    _ensure_task_access(service, actor, existing.client_id)
    previous_status = existing.status
    try:
        ticket = service.set_status(task_id, body.status)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    # Topic-sourced tasks notify the client + committee on each column move.
    if existing.topic_id and previous_status != ticket.status:
        notify_management_status_changed(
            db,
            client_id=existing.client_id,
            building_name=existing.client_name,
            subject=existing.subject,
            previous_status=previous_status,
            next_status=ticket.status,
            actor_name=_actor_name(db, actor.user_id),
        )
    return _task_response(ticket)


@router.post("/tasks/{task_id}/completion", response_model=ManagementTaskResponse)
def submit_management_completion(
    task_id: str,
    body: SubmitManagementCompletionRequest,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "reply")),
    db: Session = Depends(get_db),
) -> ManagementTaskResponse:
    """Administrator submits solution evidence for a topic-linked Gestión task."""
    try:
        existing = service.get_task(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    _ensure_task_access(service, actor, existing.client_id)
    if not existing.topic_id:
        raise HTTPException(
            status_code=422,
            detail="Only topic-linked Gestión tasks accept completion evidence here.",
        )
    topics = TopicService(SqlTopicRepository(db))
    try:
        completed = topics.submit_completion(
            existing.topic_id,
            note=body.note,
            attachments=[item.model_dump() for item in body.attachments],
        )
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Linked topic not found.") from error
    except InvalidTopicStatus as error:
        raise HTTPException(
            status_code=409,
            detail="Completion can only be submitted while the topic is in execution.",
        ) from error
    except CompletionAlreadySubmitted as error:
        raise HTTPException(status_code=409, detail="Completion already submitted.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    # Stay in En proceso until the committee Resultado audit decides.
    previous_status = existing.status
    ticket = existing
    if existing.status == MANAGEMENT_STATUS_TODO:
        ticket = service.set_status(task_id, MANAGEMENT_STATUS_IN_PROGRESS)
    elif existing.status == MANAGEMENT_STATUS_DONE:
        ticket = service.set_status(task_id, MANAGEMENT_STATUS_IN_PROGRESS)
    else:
        ticket = service.get_task(task_id)

    actor_name = _actor_name(db, actor.user_id)
    notify_management_completion_for_review(
        db,
        client_id=existing.client_id,
        building_name=existing.client_name,
        subject=existing.subject,
        note=body.note.strip(),
        actor_name=actor_name,
    )
    if previous_status != ticket.status:
        notify_management_status_changed(
            db,
            client_id=existing.client_id,
            building_name=existing.client_name,
            subject=existing.subject,
            previous_status=previous_status,
            next_status=ticket.status,
            actor_name=actor_name,
        )
    snapshot = _topic_completion_snapshot(db, [completed.id]).get(completed.id)
    return _task_response_from_snapshot(ticket, snapshot)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: str,
    service: ManagementService = Depends(get_management_service),
    actor: Actor = Depends(require_permission("management", "create")),
) -> None:
    """Remove a management ticket from the board."""
    try:
        existing = service.get_task(task_id)
    except TaskNotFound:
        raise HTTPException(status_code=404, detail="Ticket not found.") from None
    _ensure_task_access(service, actor, existing.client_id)
    if existing.topic_id:
        raise HTTPException(
            status_code=409,
            detail="Topic-linked Gestión tasks cannot be deleted.",
        )
    service.delete_task(task_id)
