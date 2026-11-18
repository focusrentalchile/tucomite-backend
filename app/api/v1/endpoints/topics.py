"""Topic endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import Actor, get_current_actor, get_topic_service, require_committee_member, require_permission
from app.core.database import get_db
from app.domain.topics import (
    CLOSED_STATUS_ID,
    DOING_STATUS_ID,
    OPEN_STATUS_ID,
    WAITING_STATUS_ID,
    ExecutionQuorumNotMet,
    CompletionAlreadySubmitted,
    CompletionNotSubmitted,
    CompletionQuorumNotMet,
    ConfirmationAlreadyCast,
    InvalidTopicStatus,
    InvalidVoteChoice,
    InvalidVoteOptions,
    InvalidVotingWindow,
    TopicAttachmentRecord,
    TopicConfirmationRecord,
    TopicNotFound,
    TopicOpinionRecord,
    TopicRecord,
    TopicVoteRecord,
    VoteAlreadyCast,
    VotingWindowClosed,
    execution_quorum_met,
    is_assign_ready,
    is_no_consensus,
    winning_vote_count,
)
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.client_repository import SqlClientRepository
from app.repositories.client_settings_repository import SqlClientSettingsRepository
from app.repositories.committee_repository import SqlCommitteeRepository
from app.repositories.period_repository import SqlPeriodRepository
from app.repositories.topic_repository import SqlTopicRepository
from app.services.topic_notification_email import (
    notify_topic_assign_ready,
    notify_topic_created,
    notify_topic_deleted,
    notify_topic_no_consensus,
    notify_topic_opinion,
    notify_topic_resultado_vote,
    notify_topic_status_changed,
)
from app.schemas.access import UserListResponse, UserResponse
from app.schemas.topics import (
    CastVoteRequest,
    CastVoteResponse,
    ConfirmCompletionRequest,
    ConfirmCompletionResponse,
    CreateTopicRequest,
    MoveTopicRequest,
    SeenOpinionsResponse,
    SubmitCompletionRequest,
    SubmitCompletionResponse,
    TopicAttachmentResponse,
    TopicConfirmationResponse,
    TopicListResponse,
    TopicOpinionResponse,
    TopicResponse,
    TopicVoteResponse,
    UpdateTopicRequest,
    UpsertOpinionRequest,
    UpsertOpinionResponse,
)
from app.services.access_service import PermissionPolicy
from app.services.committee_access import is_listed_committee_member
from app.services.client_settings_service import ClientSettingsService
from app.services.period_service import PeriodService
from app.services.topic_scope import list_topics_for_building
from app.services.topic_service import TopicService

MIN_COMMITTEE_FOR_VOTE = 3

router = APIRouter(tags=["topics"])


def _vote_response(vote: TopicVoteRecord) -> TopicVoteResponse:
    return TopicVoteResponse(
        id=vote.id,
        author_id=vote.author_id,
        author_name=vote.author_name,
        choice=vote.choice,
    )


def _opinion_response(
    opinion: TopicOpinionRecord,
    *,
    by_id: dict[str, TopicOpinionRecord] | None = None,
) -> TopicOpinionResponse:
    parent = by_id.get(opinion.reply_to_opinion_id) if by_id and opinion.reply_to_opinion_id else None
    return TopicOpinionResponse(
        id=opinion.id,
        author_id=opinion.author_id,
        author_name=opinion.author_name,
        body=opinion.body,
        created_at=opinion.created_at,
        reply_to_opinion_id=opinion.reply_to_opinion_id,
        reply_to_author_name=parent.author_name if parent is not None else None,
        reply_to_body=parent.body if parent is not None else None,
        audio_url=opinion.audio_url,
        audio_duration_ms=opinion.audio_duration_ms,
    )


def _opinion_responses(opinions: list[TopicOpinionRecord]) -> list[TopicOpinionResponse]:
    by_id = {item.id: item for item in opinions}
    return [_opinion_response(item, by_id=by_id) for item in opinions]


def _confirmation_response(confirmation: TopicConfirmationRecord) -> TopicConfirmationResponse:
    choice = (confirmation.choice or "yes").casefold()
    if choice not in {"yes", "no"}:
        choice = "yes"
    return TopicConfirmationResponse(
        id=confirmation.id,
        author_id=confirmation.author_id,
        author_name=confirmation.author_name,
        created_at=confirmation.created_at,
        choice=choice,  # type: ignore[arg-type]
        reason=confirmation.reason,
    )


def _attachment_response(attachment: TopicAttachmentRecord) -> TopicAttachmentResponse:
    return TopicAttachmentResponse(
        id=attachment.id,
        kind=attachment.kind,  # type: ignore[arg-type]
        name=attachment.name,
        url=attachment.url,
    )


def _topic_response(
    topic: TopicRecord,
    votes: list[TopicVoteRecord],
    opinions: list[TopicOpinionRecord] | None = None,
    attachments: list[TopicAttachmentRecord] | None = None,
    completion_attachments: list[TopicAttachmentRecord] | None = None,
    confirmations: list[TopicConfirmationRecord] | None = None,
    *,
    assignee_role_key: str | None = None,
    unread_opinion_count: int = 0,
    opinions_last_seen_at: str | None = None,
    assign_ready: bool = False,
    no_consensus: bool = False,
    consensus_ends_at: str | None = None,
) -> TopicResponse:
    return TopicResponse(
        id=topic.id,
        title=topic.title,
        description=topic.description,
        category_key=topic.category_key,
        attachment_name=topic.attachment_name,
        decision=topic.decision,
        status_id=topic.status_id,
        priority_id=topic.priority_id,
        assignee_user_id=topic.assignee_user_id,
        assignee_role_key=assignee_role_key,
        start_date=topic.start_date,
        due_date=topic.due_date,
        vote_type=topic.vote_type if topic.vote_type in {"yes_no", "custom"} else "yes_no",  # type: ignore[arg-type]
        vote_options=[
            {"id": option.id, "label": option.label} for option in topic.vote_options
        ],
        client_id=topic.client_id,
        voting_starts_at=topic.voting_starts_at,
        voting_ends_at=topic.voting_ends_at,
        status_entered_at=topic.status_entered_at or topic.created_at,
        votes=[_vote_response(vote) for vote in votes],
        opinions=_opinion_responses(opinions or []),
        attachments=[_attachment_response(item) for item in (attachments or [])],
        completion_note=topic.completion_note,
        completion_submitted_at=topic.completion_submitted_at,
        completion_round=max(1, int(topic.completion_round or 1)),
        completion_rounds=[
            {
                "round_number": item.round_number,
                "note": item.note,
                "submitted_at": item.submitted_at,
                "closed_at": item.closed_at,
                "outcome": item.outcome if item.outcome in {"failed", "passed"} else "failed",
                "confirmations": [_confirmation_response(vote) for vote in item.confirmations],
                "attachments": [_attachment_response(file) for file in item.attachments],
            }
            for item in topic.completion_rounds
        ],
        completion_attachments=[
            _attachment_response(item) for item in (completion_attachments or [])
        ],
        confirmations=[_confirmation_response(item) for item in (confirmations or [])],
        unread_opinion_count=unread_opinion_count,
        opinions_last_seen_at=opinions_last_seen_at,
        assign_ready=assign_ready,
        has_assign_ready_alert=assign_ready,
        no_consensus=no_consensus,
        consensus_ends_at=consensus_ends_at,
    )


def _parse_naive_utc(value: str | None) -> datetime | None:
    """Parse a stored ISO instant into a naive UTC datetime for comparisons."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def unread_opinion_count_for(
    opinions: list[TopicOpinionRecord],
    *,
    actor_id: str,
    last_seen_at: str | None,
) -> int:
    """Count opinions from other people written after the actor last opened the section."""
    seen = _parse_naive_utc(last_seen_at)
    total = 0
    for opinion in opinions:
        if opinion.author_id == actor_id:
            continue
        created = _parse_naive_utc(opinion.created_at)
        if seen is None or created is None or created > seen:
            total += 1
    return total


def _assignee_role_map(db: Session, topics: list[TopicRecord]) -> dict[str, str]:
    """Map assignee user ids to role keys for the listed topics."""
    ids = {topic.assignee_user_id for topic in topics if topic.assignee_user_id}
    if not ids:
        return {}
    access = SqlAccessRepository(db)
    roles = {role.id: role.name for role in access.list_roles()}
    out: dict[str, str] = {}
    for user in access.list_users():
        if user.id not in ids:
            continue
        role_name = roles.get(user.role_id, "")
        if role_name:
            out[user.id] = role_name
    return out


def _topics_for_open_period(
    service: TopicService,
    db: Session,
    *,
    client_id: str,
) -> list[TopicRecord]:
    """Return the building's topics (shared by committee and owner of the same client_id)."""
    return list_topics_for_building(service, SqlPeriodRepository(db), client_id=client_id)


def _publish_agreement_best_effort(
    db: Session,
    *,
    topic_id: str,
    client_id: str | None,
) -> None:
    """Publish the PDF agreement after a topic closes. Never undoes the close.

    Uses a SAVEPOINT so a PDF/DB failure cannot poison the request session
    (which would break GET /topics with PendingRollbackError).
    """
    try:
        from app.repositories.agreement_repository import SqlAgreementRepository
        from app.repositories.client_repository import SqlClientRepository
        from app.services.agreement_service import AgreementService

        with db.begin_nested():
            AgreementService(
                SqlAgreementRepository(db),
                SqlTopicRepository(db),
                SqlClientRepository(db),
            ).publish_from_topic(topic_id, client_id=client_id)
    except Exception:  # noqa: BLE001 — closing must stick even if the PDF fails
        logger.exception("Agreement publish failed for topic %s", topic_id)


@router.get("/topics/assignees", response_model=UserListResponse)
def list_topic_assignees(
    actor: Actor = Depends(require_permission("matters", "comment")),
    _: Actor = Depends(require_committee_member),
    db: Session = Depends(get_db),
) -> UserListResponse:
    """People a committee voter may assign when starting execution.

    Committee members do not get ``users.view`` (Usuarios), so this lean list is
    gated by matters.comment + committee membership instead.
    """
    if not actor.is_super_admin and not actor.client_id:
        raise HTTPException(status_code=403, detail="Forbidden.")
    access = SqlAccessRepository(db)
    roles = {role.id: role for role in access.list_roles()}
    admin_id = None
    if actor.client_id:
        client = SqlClientRepository(db).get_client(actor.client_id)
        admin_id = None if client is None else client.admin_user_id
    items: list[UserResponse] = []
    for user in access.list_users():
        role = roles.get(user.role_id)
        if role is not None and role.system:
            continue
        if actor.is_super_admin or (actor.client_id and user.client_id == actor.client_id):
            items.append(
                UserResponse(
                    id=user.id,
                    full_name=user.full_name,
                    email=user.email,
                    role_id=user.role_id,
                    role_key=role.name if role is not None else "",
                    protected=bool(admin_id and user.id == admin_id),
                    client_id=user.client_id,
                    floor_number=user.floor_number,
                    apartment_number=user.apartment_number,
                    rut=user.rut or "",
                )
            )
    items.sort(key=lambda item: item.full_name.casefold())
    return UserListResponse(items=items)


@router.get("/topics", response_model=TopicListResponse)
def read_topics(
    service: TopicService = Depends(get_topic_service),
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> TopicListResponse:
    """Return open-period topics with votes, opinions, and attachments."""
    if not actor.client_id:
        return TopicListResponse(items=[])
    topics = _topics_for_open_period(service, db, client_id=actor.client_id)
    committee_size = SqlCommitteeRepository(db).count_voter_seats(actor.client_id)
    healed: list = []
    for topic in topics:
        previous_status = topic.status_id
        try:
            next_topic = service.seal_failed_completion_if_needed(
                topic,
                committee_size=committee_size,
            )
        except Exception:
            logger.exception("Topic heal failed for %s", topic.id)
            try:
                db.rollback()
            except Exception:
                pass
            healed.append(topic)
            continue
        if next_topic.status_id == CLOSED_STATUS_ID:
            # Publish (or retry) the acta for every closed topic, including already-closed ones.
            try:
                _publish_agreement_best_effort(
                    db,
                    topic_id=next_topic.id,
                    client_id=actor.client_id or next_topic.client_id,
                )
            except Exception:  # noqa: BLE001 — never block the Temas board
                logger.exception("Agreement heal publish crashed for %s", next_topic.id)
        healed.append(next_topic)
    topics = healed
    topic_ids = [topic.id for topic in topics]
    votes = service.list_votes_for_topics(topic_ids)
    opinions = service.list_opinions_for_topics(topic_ids)
    attachments = service.list_attachments_for_topics(topic_ids)
    completion_attachments = service.list_completion_attachments_for_topics(topic_ids)
    confirmations = service.list_confirmations_for_topics(topic_ids)
    by_topic: dict[str, list[TopicVoteRecord]] = {topic.id: [] for topic in topics}
    opinions_by_topic: dict[str, list[TopicOpinionRecord]] = {topic.id: [] for topic in topics}
    attachments_by_topic: dict[str, list[TopicAttachmentRecord]] = {topic.id: [] for topic in topics}
    completion_by_topic: dict[str, list[TopicAttachmentRecord]] = {topic.id: [] for topic in topics}
    confirmations_by_topic: dict[str, list[TopicConfirmationRecord]] = {
        topic.id: [] for topic in topics
    }
    for vote in votes:
        by_topic.setdefault(vote.topic_id, []).append(vote)
    for opinion in opinions:
        opinions_by_topic.setdefault(opinion.topic_id, []).append(opinion)
    for attachment in attachments:
        attachments_by_topic.setdefault(attachment.topic_id, []).append(attachment)
    for attachment in completion_attachments:
        completion_by_topic.setdefault(attachment.topic_id, []).append(attachment)
    for confirmation in confirmations:
        confirmations_by_topic.setdefault(confirmation.topic_id, []).append(confirmation)
    # Notify once when everyone voted without a majority, or vote hours ended without one.
    topics_repo = SqlTopicRepository(db)
    for topic in topics:
        topic_votes = by_topic.get(topic.id, [])
        if not is_no_consensus(topic, topic_votes, committee_size):
            continue
        if topic.no_consensus_notified_at:
            continue
        try:
            with db.begin_nested():
                notify_topic_no_consensus(
                    db,
                    topic=topic,
                    client_id=actor.client_id or topic.client_id,
                )
                notified_at = datetime.now(timezone.utc).isoformat()
                topics_repo.mark_no_consensus_notified(topic.id, notified_at)
        except Exception:  # noqa: BLE001 — board must load even if mail fails
            logger.exception("No-consensus notify failed for topic %s", topic.id)
    assignee_roles = _assignee_role_map(db, topics)
    reads = service.list_opinion_reads(actor.user_id, topic_ids)
    return TopicListResponse(
        items=[
            _topic_response(
                topic,
                by_topic.get(topic.id, []),
                opinions_by_topic.get(topic.id, []),
                attachments_by_topic.get(topic.id, []),
                completion_by_topic.get(topic.id, []),
                confirmations_by_topic.get(topic.id, []),
                assignee_role_key=(
                    assignee_roles.get(topic.assignee_user_id)
                    if topic.assignee_user_id
                    else None
                ),
                unread_opinion_count=unread_opinion_count_for(
                    opinions_by_topic.get(topic.id, []),
                    actor_id=actor.user_id,
                    last_seen_at=reads.get(topic.id),
                ),
                opinions_last_seen_at=reads.get(topic.id),
                assign_ready=is_assign_ready(
                    topic,
                    by_topic.get(topic.id, []),
                    committee_size,
                ),
                no_consensus=is_no_consensus(
                    topic,
                    by_topic.get(topic.id, []),
                    committee_size,
                ),
                consensus_ends_at=None,
            )
            for topic in topics
        ],
    )


@router.post("/topics", response_model=TopicResponse, status_code=201)
def create_topic(
    body: CreateTopicRequest,
    service: TopicService = Depends(get_topic_service),
    actor: Actor = Depends(require_permission("matters", "create")),
    _: Actor = Depends(require_committee_member),
    db: Session = Depends(get_db),
) -> TopicResponse:
    """Create a topic in status 1 (open). Only committee members may create."""
    if not actor.client_id:
        raise HTTPException(status_code=422, detail="Building context is required.")
    open_period = PeriodService(SqlPeriodRepository(db)).ensure_current_month_open(actor.client_id)
    if open_period is None:
        raise HTTPException(status_code=409, detail="Period is not open.")
    try:
        topic = service.create_topic(
            body.title,
            body.description,
            body.category_key,
            body.attachment_name,
            body.decision,
            body.priority_id,
            period_id=open_period.id,
            attachments=[item.model_dump() for item in body.attachments],
            vote_type=body.vote_type,
            vote_options=[item.model_dump() for item in body.vote_options],
            client_id=actor.client_id,
            voting_starts_at=body.voting_starts_at,
            voting_ends_at=body.voting_ends_at,
            default_window_hours=ClientSettingsService(
                SqlClientSettingsRepository(db),
            ).hours_for_priority(actor.client_id, body.priority_id),
        )
    except InvalidVoteOptions as error:
        raise HTTPException(
            status_code=422,
            detail="Custom polls need at least two answer options.",
        ) from error
    except InvalidVotingWindow as error:
        raise HTTPException(
            status_code=422,
            detail="Voting window must have valid dates and end after it starts.",
        ) from error
    stored = service.list_attachments_for_topics([topic.id])
    actor_user = SqlAccessRepository(db).get_user(actor.user_id)
    notify_topic_created(
        db,
        topic=topic,
        client_id=actor.client_id,
        actor_name=actor_user.full_name if actor_user else "",
    )
    return _topic_response(topic, [], attachments=stored)


@router.patch("/topics/{topic_id}", response_model=TopicResponse)
def update_topic(
    topic_id: str,
    body: UpdateTopicRequest,
    service: TopicService = Depends(get_topic_service),
    _: Actor = Depends(require_permission("matters", "create")),
    __: Actor = Depends(require_committee_member),
) -> TopicResponse:
    """Update the editable fields of one topic. Only committee members may edit."""
    try:
        topic = service.update_topic(
            topic_id,
            body.title,
            body.description,
            body.category_key,
            body.attachment_name,
            body.decision,
            body.priority_id,
            attachments=[item.model_dump() for item in body.attachments],
            vote_type=body.vote_type,
            vote_options=[item.model_dump() for item in body.vote_options],
        )
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    except InvalidVoteOptions as error:
        raise HTTPException(
            status_code=422,
            detail="Custom polls need at least two answer options.",
        ) from error
    votes = service.list_votes_for_topics([topic.id])
    opinions = service.list_opinions_for_topics([topic.id])
    stored = service.list_attachments_for_topics([topic.id])
    completion = service.list_completion_attachments_for_topics([topic.id])
    confirmations = service.list_confirmations_for_topics([topic.id])
    return _topic_response(topic, votes, opinions, stored, completion, confirmations)


@router.patch("/topics/{topic_id}/status", response_model=TopicResponse)
def move_topic(
    topic_id: str,
    body: MoveTopicRequest,
    service: TopicService = Depends(get_topic_service),
    actor: Actor = Depends(require_permission("matters", "comment")),
    _: Actor = Depends(require_committee_member),
    db: Session = Depends(get_db),
) -> TopicResponse:
    """Move one topic. Going to execution requires a responsible person and due date.

    Any committee member (or the client owner) may assign execution once the vote majority
    is met, and may close when Resultado has a Sí majority. Other column moves still need
    ``matters.create``.
    """
    if body.status_id not in {DOING_STATUS_ID, CLOSED_STATUS_ID} and not PermissionPolicy().allows(
        actor.permissions,
        "matters",
        "create",
    ):
        raise HTTPException(status_code=403, detail="Forbidden.")
    from app.repositories.agreement_repository import SqlAgreementRepository
    from app.repositories.client_repository import SqlClientRepository
    from app.repositories.management_repository import SqlManagementRepository
    from app.repositories.notification_repository import SqlNotificationRepository
    from app.services.agreement_service import AgreementService
    from app.services.management_service import ManagementService
    from app.services.management_task_email import notify_management_task_assigned_email

    if body.status_id == DOING_STATUS_ID:
        if not body.assignee_user_id or not body.start_date or not body.due_date:
            raise HTTPException(
                status_code=422,
                detail="Assignee, start date, and due date are required to start execution.",
            )
        if body.due_date < body.start_date:
            raise HTTPException(
                status_code=422,
                detail="Due date cannot be before start date.",
            )
    committee_size = SqlCommitteeRepository(db).count_voter_seats(actor.client_id)
    previous = SqlTopicRepository(db).get_topic(topic_id)
    previous_status_id = previous.status_id if previous is not None else None
    try:
        topic = service.move_topic(topic_id, body.status_id, committee_size=committee_size)
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    except InvalidTopicStatus as error:
        raise HTTPException(status_code=422, detail="Invalid topic status.") from error
    except CompletionNotSubmitted as error:
        raise HTTPException(
            status_code=409,
            detail="Completion evidence is required before closing.",
        ) from error
    except CompletionQuorumNotMet as error:
        raise HTTPException(
            status_code=409,
            detail="More than 50% of the committee must confirm completion before closing.",
        ) from error
    except ExecutionQuorumNotMet as error:
        raise HTTPException(
            status_code=409,
            detail="More than 50% of the committee must approve before assigning execution.",
        ) from error

    if previous_status_id is not None and previous_status_id != topic.status_id:
        actor_user = SqlAccessRepository(db).get_user(actor.user_id)
        notify_topic_status_changed(
            db,
            topic=topic,
            previous_status_id=previous_status_id,
            client_id=actor.client_id,
            actor_name=actor_user.full_name if actor_user else "",
        )

    if body.status_id == CLOSED_STATUS_ID:
        AgreementService(
            SqlAgreementRepository(db),
            SqlTopicRepository(db),
            SqlClientRepository(db),
        ).publish_from_topic(topic_id, client_id=actor.client_id)
        # Linked Gestión work can move to Finalizadas once the topic closes.
        if actor.client_id:
            access = SqlAccessRepository(db)
            management = ManagementService(
                SqlManagementRepository(db),
                access=access,
                notifications=SqlNotificationRepository(db),
            )
            for item in management.list_tasks(client_id=actor.client_id):
                if item.topic_id == topic_id and item.status != "done":
                    management.set_status(item.id, "done")

    if body.status_id == DOING_STATUS_ID and body.assignee_user_id and body.start_date and body.due_date:
        SqlTopicRepository(db).save_topic_assignment(
            topic_id,
            body.assignee_user_id,
            body.due_date,
            start_date=body.start_date,
        )
        topic = next(item for item in service.list_topics() if item.id == topic_id)
        client = SqlClientRepository(db).get_client(actor.client_id) if actor.client_id else None
        access = SqlAccessRepository(db)
        assignee = access.get_user(body.assignee_user_id)
        assignee_role = access.get_role(assignee.role_id) if assignee else None
        assignee_role_name = (assignee_role.name if assignee_role else "").casefold()
        # Gestión card for the building owner, administrator, or caretaker assignee.
        should_open_management = client is not None and (
            body.assignee_user_id == client.admin_user_id
            or assignee_role_name in {"administrator", "caretaker"}
        )
        if should_open_management:
            actor_user = access.get_user(actor.user_id)
            management = ManagementService(
                SqlManagementRepository(db),
                access=access,
                notifications=SqlNotificationRepository(db),
            )
            existing = next(
                (
                    item
                    for item in management.list_tasks(client_id=actor.client_id)
                    if item.topic_id == topic.id
                ),
                None,
            )
            if existing is None:
                topic_attachments = service.list_attachments_for_topics([topic.id])
                created_task = management.create_task(
                    subject=topic.title,
                    body=topic.description or topic.decision,
                    created_by_user_id=actor.user_id,
                    created_by_name=actor_user.full_name if actor_user else "",
                    client_id=actor.client_id,
                    client_name=client.name,
                    from_staff=False,
                    priority_id=topic.priority_id,
                    due_date=body.due_date,
                    assignee_user_id=body.assignee_user_id,
                    topic_id=topic.id,
                    attachments=[
                        {"kind": item.kind, "name": item.name, "url": item.url}
                        for item in topic_attachments
                    ]
                    or None,
                )
                # Email every approved workspace administrator (and the assignee if distinct).
                emailed: set[str] = set()
                for admin in management.list_building_administrators(actor.client_id):
                    if admin.status != "approved" or not admin.email or admin.email in emailed:
                        continue
                    emailed.add(admin.email)
                    notify_management_task_assigned_email(
                        db,
                        to_email=admin.email,
                        to_name=admin.full_name,
                        building_name=client.name,
                        subject=created_task.subject,
                        body=topic.description or topic.decision,
                        actor_name=actor_user.full_name if actor_user else "",
                    )
                if assignee is not None and assignee.email and assignee.email not in emailed:
                    notify_management_task_assigned_email(
                        db,
                        to_email=assignee.email,
                        to_name=assignee.full_name,
                        building_name=client.name,
                        subject=created_task.subject,
                        body=topic.description or topic.decision,
                        actor_name=actor_user.full_name if actor_user else "",
                    )

    votes = service.list_votes_for_topics([topic_id])
    refreshed = next((item for item in service.list_topics() if item.id == topic_id), topic)
    completion = service.list_completion_attachments_for_topics([topic_id])
    confirmations = service.list_confirmations_for_topics([topic_id])
    return _topic_response(
        refreshed,
        votes,
        completion_attachments=completion,
        confirmations=confirmations,
    )


@router.delete("/topics/{topic_id}", status_code=204)
def delete_topic(
    topic_id: str,
    service: TopicService = Depends(get_topic_service),
    actor: Actor = Depends(require_permission("matters", "create")),
    _: Actor = Depends(require_committee_member),
    db: Session = Depends(get_db),
) -> None:
    """Passively archive one open topic and notify the client and committee."""
    topic = SqlTopicRepository(db).get_topic(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found.") from None
    if topic.status_id != OPEN_STATUS_ID:
        raise HTTPException(
            status_code=409,
            detail="Only topics in Abiertos can be deleted.",
        )
    access = SqlAccessRepository(db)
    user = access.get_user(actor.user_id)
    actor_name = user.full_name if user is not None else "Alguien del comité"
    try:
        service.delete_topic(topic_id)
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    notify_topic_deleted(
        db,
        topic=topic,
        client_id=actor.client_id or topic.client_id,
        actor_name=actor_name,
    )


@router.post("/topics/{topic_id}/votes", response_model=CastVoteResponse)
def cast_vote(
    topic_id: str,
    body: CastVoteRequest,
    service: TopicService = Depends(get_topic_service),
    actor: Actor = Depends(require_permission("matters", "comment")),
    _: Actor = Depends(require_committee_member),
    db: Session = Depends(get_db),
) -> CastVoteResponse:
    """Store or update the actor's vote while the topic is open or waiting."""
    if not is_listed_committee_member(db, actor.user_id):
        raise HTTPException(status_code=403, detail="Only committee voters may vote.")
    access = SqlAccessRepository(db)
    user = next((item for item in access.list_users() if item.id == actor.user_id), None)
    if user is None:
        raise HTTPException(status_code=503, detail="Current user is not available.")
    member_count = SqlCommitteeRepository(db).count_voter_seats(actor.client_id)
    if member_count < MIN_COMMITTEE_FOR_VOTE:
        raise HTTPException(
            status_code=409,
            detail="At least three committee members are required to vote.",
        )
    settings_service = ClientSettingsService(SqlClientSettingsRepository(db))
    previous = SqlTopicRepository(db).get_topic(topic_id)
    previous_status_id = previous.status_id if previous is not None else None
    reopen_hours = None
    if previous is not None and actor.client_id:
        reopen_hours = settings_service.hours_for_priority(actor.client_id, previous.priority_id)
    votes_before = service.list_votes_for_topics([topic_id]) if previous is not None else []
    quorum_before = previous is not None and execution_quorum_met(
        winning_vote_count(previous, votes_before),
        member_count,
    )
    try:
        topic, vote = service.cast_vote(
            topic_id,
            author_id=actor.user_id,
            author_name=user.full_name,
            choice=body.choice,
            committee_size=member_count,
            reopen_window_hours=reopen_hours,
        )
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    except InvalidVoteChoice as error:
        raise HTTPException(status_code=422, detail="Invalid vote choice for this poll.") from error
    except VoteAlreadyCast as error:
        raise HTTPException(status_code=409, detail="Vote already cast.") from error
    except VotingWindowClosed as error:
        detail = (
            "Voting has not started yet."
            if error.reason == "not_started"
            else "Voting has ended."
        )
        raise HTTPException(status_code=409, detail=detail) from error
    # Open -> Waiting after a vote is silent; the committee only hears when the vote majority
    # is reached (assign-ready email + bell).
    if (
        previous_status_id is not None
        and previous_status_id != topic.status_id
        and not (previous_status_id == OPEN_STATUS_ID and topic.status_id == WAITING_STATUS_ID)
    ):
        notify_topic_status_changed(
            db,
            topic=topic,
            previous_status_id=previous_status_id,
            client_id=actor.client_id,
            actor_name=user.full_name,
        )
    votes_after = [item for item in votes_before if item.author_id != vote.author_id] + [vote]
    if not quorum_before and is_assign_ready(topic, votes_after, member_count):
        notify_topic_assign_ready(
            db,
            topic=topic,
            client_id=actor.client_id or topic.client_id,
            actor_name=user.full_name,
        )
    elif is_no_consensus(topic, votes_after, member_count) and not topic.no_consensus_notified_at:
        try:
            notify_topic_no_consensus(
                db,
                topic=topic,
                client_id=actor.client_id or topic.client_id,
                actor_name=user.full_name,
            )
            SqlTopicRepository(db).mark_no_consensus_notified(
                topic.id,
                datetime.now(timezone.utc).isoformat(),
            )
        except Exception:  # noqa: BLE001 — vote must succeed even if mail fails
            logger.exception("No-consensus notify failed after vote on %s", topic.id)
    return CastVoteResponse(
        topic_id=topic.id,
        status_id=topic.status_id,
        vote=_vote_response(vote),
    )


@router.post("/topics/{topic_id}/opinions", response_model=UpsertOpinionResponse)
def upsert_opinion(
    topic_id: str,
    body: UpsertOpinionRequest,
    service: TopicService = Depends(get_topic_service),
    actor: Actor = Depends(require_permission("matters", "comment")),
    _: Actor = Depends(require_committee_member),
    db: Session = Depends(get_db),
) -> UpsertOpinionResponse:
    """Append an opinion message. Listed voters and the client may write many."""
    access = SqlAccessRepository(db)
    user = next((item for item in access.list_users() if item.id == actor.user_id), None)
    if user is None:
        raise HTTPException(status_code=503, detail="Current user is not available.")
    prior_opinions = service.list_opinions_for_topics([topic_id])
    is_first_opinion = len(prior_opinions) == 0
    try:
        opinion = service.create_opinion(
            topic_id,
            author_id=actor.user_id,
            author_name=user.full_name,
            body=body.body,
            reply_to_opinion_id=body.reply_to_opinion_id,
            audio_url=body.audio_url,
            audio_duration_ms=body.audio_duration_ms,
        )
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    except InvalidTopicStatus as error:
        raise HTTPException(status_code=409, detail="Closed topics are read-only for opinions.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        topic = SqlTopicRepository(db).get_topic(topic_id)
        if topic is not None:
            notify_topic_opinion(
                db,
                topic=topic,
                author_id=actor.user_id,
                author_name=user.full_name,
                client_id=actor.client_id or topic.client_id,
                send_email=is_first_opinion,
            )
    except Exception:  # noqa: BLE001 — never block writing an opinion on notices
        pass
    by_id = {item.id: item for item in [*prior_opinions, opinion]}
    return UpsertOpinionResponse(
        topic_id=topic_id,
        opinion=_opinion_response(opinion, by_id=by_id),
    )


@router.post("/topics/{topic_id}/opinions/seen", response_model=SeenOpinionsResponse)
def mark_opinions_seen(
    topic_id: str,
    service: TopicService = Depends(get_topic_service),
    actor: Actor = Depends(require_permission("matters", "comment")),
    _: Actor = Depends(require_committee_member),
) -> SeenOpinionsResponse:
    """Mark every current opinion of one topic as seen for the signed-in person."""
    try:
        seen_at = service.mark_opinions_seen(topic_id, actor.user_id)
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    return SeenOpinionsResponse(topic_id=topic_id, last_seen_at=seen_at)


@router.delete("/topics/{topic_id}/opinions/{opinion_id}", status_code=204)
def delete_opinion(
    topic_id: str,
    opinion_id: str,
    service: TopicService = Depends(get_topic_service),
    actor: Actor = Depends(require_permission("matters", "comment")),
    _: Actor = Depends(require_committee_member),
) -> None:
    """Delete one opinion written by the signed-in person."""
    try:
        service.delete_opinion(topic_id, opinion_id, actor.user_id)
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Opinion not found.") from error
    except InvalidTopicStatus as error:
        raise HTTPException(status_code=409, detail="Closed topics are read-only for opinions.") from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@router.post("/topics/{topic_id}/completion", response_model=SubmitCompletionResponse)
def submit_completion(
    topic_id: str,
    body: SubmitCompletionRequest,
    service: TopicService = Depends(get_topic_service),
    actor: Actor = Depends(require_permission("matters", "create")),
    _: Actor = Depends(require_committee_member),
    db: Session = Depends(get_db),
) -> SubmitCompletionResponse:
    """Store the solution note and evidence for a topic in execution."""
    current = SqlTopicRepository(db).get_topic(topic_id)
    if current is not None and current.assignee_user_id:
        access = SqlAccessRepository(db)
        assignee = access.get_user(current.assignee_user_id)
        role = access.get_role(assignee.role_id) if assignee else None
        role_name = (role.name if role else "").casefold()
        if role_name not in {"committee", "client"}:
            raise HTTPException(
                status_code=409,
                detail="When the assignee is not the client or committee, completion must be submitted from Gestión.",
            )
    try:
        topic = service.submit_completion(
            topic_id,
            note=body.note,
            attachments=[item.model_dump() for item in body.attachments],
        )
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    except InvalidTopicStatus as error:
        raise HTTPException(
            status_code=409,
            detail="Completion can only be submitted while the topic is in execution.",
        ) from error
    except CompletionAlreadySubmitted as error:
        raise HTTPException(status_code=409, detail="Completion already submitted.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    completion = service.list_completion_attachments_for_topics([topic.id])
    confirmations = service.list_confirmations_for_topics([topic.id])
    votes = service.list_votes_for_topics([topic.id])
    return SubmitCompletionResponse(
        topic=_topic_response(
            topic,
            votes,
            completion_attachments=completion,
            confirmations=confirmations,
        ),
    )


@router.post("/topics/{topic_id}/confirmations", response_model=ConfirmCompletionResponse)
def confirm_completion(
    topic_id: str,
    body: ConfirmCompletionRequest,
    service: TopicService = Depends(get_topic_service),
    actor: Actor = Depends(require_permission("matters", "comment")),
    _: Actor = Depends(require_committee_member),
    db: Session = Depends(get_db),
) -> ConfirmCompletionResponse:
    """Record a committee Resultado vote (resolved yes/no)."""
    if not is_listed_committee_member(db, actor.user_id):
        raise HTTPException(status_code=403, detail="Only committee voters may confirm.")
    access = SqlAccessRepository(db)
    user = next((item for item in access.list_users() if item.id == actor.user_id), None)
    if user is None:
        raise HTTPException(status_code=503, detail="Current user is not available.")
    committee_size = SqlCommitteeRepository(db).count_voter_seats(actor.client_id)
    try:
        topic, confirmation = service.confirm_completion(
            topic_id,
            author_id=actor.user_id,
            author_name=user.full_name,
            choice=body.choice,
            reason=body.reason,
            committee_size=committee_size,
        )
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    except InvalidTopicStatus as error:
        raise HTTPException(
            status_code=409,
            detail="Completion can only be confirmed while the topic is in execution.",
        ) from error
    except CompletionNotSubmitted as error:
        raise HTTPException(
            status_code=409,
            detail="Completion evidence is required before confirming.",
        ) from error
    except ConfirmationAlreadyCast as error:
        raise HTTPException(status_code=409, detail="Completion already confirmed.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    notify_topic_resultado_vote(
        db,
        topic=topic,
        confirmation=confirmation,
        client_id=actor.client_id or topic.client_id,
        actor_name=user.full_name,
    )
    if topic.status_id == CLOSED_STATUS_ID:
        building_id = actor.client_id or topic.client_id
        _publish_agreement_best_effort(
            db,
            topic_id=topic_id,
            client_id=building_id,
        )
        try:
            from app.repositories.management_repository import SqlManagementRepository
            from app.repositories.notification_repository import SqlNotificationRepository
            from app.services.management_service import ManagementService

            if building_id:
                access_repo = SqlAccessRepository(db)
                management = ManagementService(
                    SqlManagementRepository(db),
                    access=access_repo,
                    notifications=SqlNotificationRepository(db),
                )
                for item in management.list_tasks(client_id=building_id):
                    if item.topic_id == topic_id and item.status != "done":
                        management.set_status(item.id, "done")
        except Exception:  # noqa: BLE001 — topic already closed
            logger.exception("Gestión done-sync failed for topic %s", topic_id)
        try:
            notify_topic_status_changed(
                db,
                topic=topic,
                previous_status_id=DOING_STATUS_ID,
                client_id=building_id,
                actor_name=user.full_name,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Close status email failed for topic %s", topic_id)
    completion = service.list_completion_attachments_for_topics([topic_id])
    confirmations = service.list_confirmations_for_topics([topic_id])
    return ConfirmCompletionResponse(
        topic_id=topic_id,
        confirmation=_confirmation_response(confirmation),
        topic=_topic_response(topic, [], [], [], completion, confirmations),
    )
