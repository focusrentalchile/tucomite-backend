"""Topic endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_current_actor, get_topic_service, require_committee_member, require_permission
from app.core.database import get_db
from app.domain.topics import (
    InvalidTopicStatus,
    InvalidVoteChoice,
    TopicNotFound,
    TopicRecord,
    TopicVoteRecord,
    VoteAlreadyCast,
)
from app.repositories.access_repository import SqlAccessRepository
from app.schemas.topics import (
    CastVoteRequest,
    CastVoteResponse,
    CreateTopicRequest,
    MoveTopicRequest,
    TopicListResponse,
    TopicResponse,
    TopicVoteResponse,
    UpdateTopicRequest,
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


def _topic_response(topic: TopicRecord, votes: list[TopicVoteRecord]) -> TopicResponse:
    return TopicResponse(
        id=topic.id,
        title=topic.title,
        description=topic.description,
        category_key=topic.category_key,
        attachment_name=topic.attachment_name,
        decision=topic.decision,
        status_id=topic.status_id,
        priority_id=topic.priority_id,
        votes=[_vote_response(vote) for vote in votes],
    )


@router.get("/topics", response_model=TopicListResponse)
def read_topics(
    service: TopicService = Depends(get_topic_service),
    _: Actor = Depends(get_current_actor),
) -> TopicListResponse:
    """Return every topic with its votes. Any signed-in person may look."""
    topics = service.list_topics()
    votes = service.list_votes_for_topics([topic.id for topic in topics])
    by_topic: dict[str, list[TopicVoteRecord]] = {topic.id: [] for topic in topics}
    for vote in votes:
        by_topic.setdefault(vote.topic_id, []).append(vote)
    return TopicListResponse(
        items=[_topic_response(topic, by_topic.get(topic.id, [])) for topic in topics],
    )


@router.post("/topics", response_model=TopicResponse, status_code=201)
def create_topic(
    body: CreateTopicRequest,
    service: TopicService = Depends(get_topic_service),
    _: Actor = Depends(require_permission("matters", "create")),
    __: Actor = Depends(require_committee_member),
) -> TopicResponse:
    """Create a topic in status 1 (open). Only committee members may create."""
    topic = service.create_topic(
        body.title,
        body.description,
        body.category_key,
        body.attachment_name,
        body.decision,
        body.priority_id,
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
    _: Actor = Depends(require_permission("matters", "create")),
    __: Actor = Depends(require_committee_member),
) -> TopicResponse:
    """Move one topic to another board column. Only committee members may move."""
    try:
        topic = service.move_topic(topic_id, body.status_id)
    except TopicNotFound as error:
        raise HTTPException(status_code=404, detail="Topic not found.") from error
    except InvalidTopicStatus as error:
        raise HTTPException(status_code=422, detail="Invalid topic status.") from error
    votes = service.list_votes_for_topics([topic.id])
    return _topic_response(topic, votes)


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
    """Store the actor's first vote. Only committee members may vote."""
    access = SqlAccessRepository(db)
    user = next((item for item in access.list_users() if item.id == actor.user_id), None)
    if user is None:
        raise HTTPException(status_code=503, detail="Current user is not available.")
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
