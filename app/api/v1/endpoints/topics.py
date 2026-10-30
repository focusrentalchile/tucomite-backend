"""Topic endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_current_actor, get_topic_service, require_committee_member, require_permission
from app.core.database import get_db
from app.domain.topics import (
    InvalidTopicStatus,
    InvalidVoteChoice,
    TopicNotFound,
    TopicOpinionRecord,
    TopicRecord,
    TopicVoteRecord,
    VoteAlreadyCast,
)
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.committee_repository import SqlCommitteeRepository
from app.repositories.period_repository import SqlPeriodRepository
from app.repositories.topic_repository import SqlTopicRepository
from app.services.committee_access import is_listed_committee_member
from app.services.period_service import PeriodService

MIN_COMMITTEE_FOR_VOTE = 3
from app.schemas.topics import (
    CastVoteRequest,
    CastVoteResponse,
    CreateTopicRequest,
    MoveTopicRequest,
    TopicListResponse,
    TopicOpinionResponse,
    TopicResponse,
    TopicVoteResponse,
    UpdateTopicRequest,
    UpsertOpinionRequest,
    UpsertOpinionResponse,
)
from app.services.topic_service import TopicService

router = APIRouter(tags=["topics"])


def _vote_response(vote: TopicVoteRecord) -> TopicVoteResponse:
    return TopicVoteResponse(
        id=vote.id,
        author_id=vote.author_id,
        author_name=vote.author_name,
        choice=vote.choice,  # type: ignore[arg-type]
    )


def _opinion_response(opinion: TopicOpinionRecord) -> TopicOpinionResponse:
    return TopicOpinionResponse(
        id=opinion.id,
        author_id=opinion.author_id,
        author_name=opinion.author_name,
        body=opinion.body,
        created_at=opinion.created_at,
    )


def _topic_response(
    topic: TopicRecord,
    votes: list[TopicVoteRecord],
    opinions: list[TopicOpinionRecord] | None = None,
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
        start_date=topic.start_date,
        due_date=topic.due_date,
        votes=[_vote_response(vote) for vote in votes],
        opinions=[_opinion_response(item) for item in (opinions or [])],
    )


def _topics_for_open_period(
    service: TopicService,
    db: Session,
) -> list[TopicRecord]:
    """Return topics for the open period, backfilling legacy rows without period_id."""
    open_period = PeriodService(SqlPeriodRepository(db)).ensure_current_month_open()
    topics = service.list_topics()
    if open_period is None:
        return []
    scoped: list[TopicRecord] = []
    for topic in topics:
        if topic.period_id is None:
            filled = TopicRecord(
                id=topic.id,
                title=topic.title,
                description=topic.description,
                category_key=topic.category_key,
                attachment_name=topic.attachment_name,
                decision=topic.decision,
                status_id=topic.status_id,
                priority_id=topic.priority_id,
                assignee_user_id=topic.assignee_user_id,
                start_date=topic.start_date,
                due_date=topic.due_date,
                created_at=topic.created_at,
                closed_at=topic.closed_at,
                period_id=open_period.id,
            )
            SqlTopicRepository(db).save_topic(filled)
            scoped.append(filled)
            continue
        if topic.period_id == open_period.id:
            scoped.append(topic)
    return scoped


@router.get("/topics", response_model=TopicListResponse)
def read_topics(
    service: TopicService = Depends(get_topic_service),
    _: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> TopicListResponse:
    """Return open-period topics with votes and opinions. Any signed-in person may look."""
    topics = _topics_for_open_period(service, db)
    topic_ids = [topic.id for topic in topics]
    votes = service.list_votes_for_topics(topic_ids)
    opinions = service.list_opinions_for_topics(topic_ids)
    by_topic: dict[str, list[TopicVoteRecord]] = {topic.id: [] for topic in topics}
    opinions_by_topic: dict[str, list[TopicOpinionRecord]] = {topic.id: [] for topic in topics}
    for vote in votes:
        by_topic.setdefault(vote.topic_id, []).append(vote)
    for opinion in opinions:
        opinions_by_topic.setdefault(opinion.topic_id, []).append(opinion)
    return TopicListResponse(
        items=[
            _topic_response(topic, by_topic.get(topic.id, []), opinions_by_topic.get(topic.id, []))
            for topic in topics
        ],
    )


@router.post("/topics", response_model=TopicResponse, status_code=201)
def create_topic(
    body: CreateTopicRequest,
    service: TopicService = Depends(get_topic_service),
    _: Actor = Depends(require_permission("matters", "create")),
    __: Actor = Depends(require_committee_member),
    db: Session = Depends(get_db),
) -> TopicResponse:
    """Create a topic in status 1 (open). Only committee members may create."""
    open_period = PeriodService(SqlPeriodRepository(db)).ensure_current_month_open()
    if open_period is None:
        raise HTTPException(status_code=409, detail="Period is not open.")
    topic = service.create_topic(
        body.title,
        body.description,
        body.category_key,
        body.attachment_name,
        body.decision,
        body.priority_id,
        period_id=open_period.id,
    )
    return _topic_response(topic, [])


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
        )
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    votes = service.list_votes_for_topics([topic.id])
    return _topic_response(topic, votes)


@router.patch("/topics/{topic_id}/status", response_model=TopicResponse)
def move_topic(
    topic_id: str,
    body: MoveTopicRequest,
    service: TopicService = Depends(get_topic_service),
    actor: Actor = Depends(require_permission("matters", "create")),
    _: Actor = Depends(require_committee_member),
    db: Session = Depends(get_db),
) -> TopicResponse:
    """Move one topic. Going to execution requires a responsible person and due date."""
    from app.domain.topics import DOING_STATUS_ID
    from app.repositories.client_repository import SqlClientRepository
    from app.repositories.management_repository import SqlManagementRepository
    from app.repositories.topic_repository import SqlTopicRepository
    from app.services.management_service import ManagementService

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
    try:
        topic = service.move_topic(topic_id, body.status_id)
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    except InvalidTopicStatus as error:
        raise HTTPException(status_code=422, detail="Invalid topic status.") from error

    if body.status_id == DOING_STATUS_ID and body.assignee_user_id and body.start_date and body.due_date:
        SqlTopicRepository(db).save_topic_assignment(
            topic_id,
            body.assignee_user_id,
            body.due_date,
            start_date=body.start_date,
        )
        topic = service.list_topics()
        topic = next(item for item in topic if item.id == topic_id)
        client = SqlClientRepository(db).get_client(actor.client_id) if actor.client_id else None
        if client is not None and body.assignee_user_id == client.admin_user_id:
            access = SqlAccessRepository(db)
            actor_user = access.get_user(actor.user_id)
            ManagementService(SqlManagementRepository(db)).create_task(
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
            )

    votes = service.list_votes_for_topics([topic_id])
    refreshed = next((item for item in service.list_topics() if item.id == topic_id), topic)
    return _topic_response(refreshed, votes)


@router.delete("/topics/{topic_id}", status_code=204)
def delete_topic(
    topic_id: str,
    service: TopicService = Depends(get_topic_service),
    _: Actor = Depends(require_permission("matters", "create")),
    __: Actor = Depends(require_committee_member),
) -> None:
    """Remove one topic and its votes. Only committee members may delete."""
    try:
        service.delete_topic(topic_id)
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error


@router.post("/topics/{topic_id}/votes", response_model=CastVoteResponse)
def cast_vote(
    topic_id: str,
    body: CastVoteRequest,
    service: TopicService = Depends(get_topic_service),
    actor: Actor = Depends(require_permission("matters", "comment")),
    _: Actor = Depends(require_committee_member),
    db: Session = Depends(get_db),
) -> CastVoteResponse:
    """Store the actor's first vote. Only listed committee voters may vote."""
    if not is_listed_committee_member(db, actor.user_id):
        raise HTTPException(status_code=403, detail="Only committee voters may vote.")
    access = SqlAccessRepository(db)
    user = next((item for item in access.list_users() if item.id == actor.user_id), None)
    if user is None:
        raise HTTPException(status_code=503, detail="Current user is not available.")
    member_count = len(SqlCommitteeRepository(db).list_members())
    if member_count < MIN_COMMITTEE_FOR_VOTE:
        raise HTTPException(
            status_code=409,
            detail="At least three committee members are required to vote.",
        )
    try:
        topic, vote = service.cast_vote(
            topic_id,
            author_id=actor.user_id,
            author_name=user.full_name,
            choice=body.choice,
        )
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    except InvalidVoteChoice as error:
        raise HTTPException(status_code=422, detail="Vote must be yes, no, or abstain.") from error
    except VoteAlreadyCast as error:
        raise HTTPException(status_code=409, detail="Vote already cast.") from error
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
    """Create or replace the actor's opinion. Listed voters and the client may write."""
    access = SqlAccessRepository(db)
    user = next((item for item in access.list_users() if item.id == actor.user_id), None)
    if user is None:
        raise HTTPException(status_code=503, detail="Current user is not available.")
    try:
        opinion = service.upsert_opinion(
            topic_id,
            author_id=actor.user_id,
            author_name=user.full_name,
            body=body.body,
        )
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return UpsertOpinionResponse(topic_id=topic_id, opinion=_opinion_response(opinion))
