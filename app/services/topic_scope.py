"""Decides which topics one building sees, so every member of it sees the same list."""

from app.domain.topics import CLOSED_STATUS_ID, TopicRecord
from app.repositories.period_repository import PeriodRepository
from app.services.period_service import PeriodService
from app.services.topic_service import TopicService


def list_topics_for_building(
    topics: TopicService,
    period_repository: PeriodRepository,
    *,
    client_id: str,
) -> list[TopicRecord]:
    """Return the topics of one building's open period.

    A topic belongs to the building when its own ``client_id`` matches or when its period
    does. The committee and the owner share a ``client_id``, so they always get the same
    list. Unfinished topics stranded on a closed period of the same building (or on a
    legacy period with no ``client_id``) are reclaimed into the open period and stamped
    with the building, so creates stay visible.
    """
    periods = PeriodService(period_repository)
    open_period = periods.ensure_current_month_open(client_id)
    client_period_ids = {period.id for period in periods.list_periods(client_id)}
    scoped: list[TopicRecord] = []
    for topic in topics.list_topics():
        by_client = topic.client_id == client_id
        by_period = topic.period_id in client_period_ids
        if topic.client_id and not (by_client or by_period):
            # Stamped for another building.
            continue
        if topic.period_id == open_period.id:
            if not topic.client_id:
                topic = topics.reassign_period(topic.id, open_period.id, client_id)
            scoped.append(topic)
            continue
        if topic.status_id == CLOSED_STATUS_ID:
            continue
        if by_client or by_period:
            scoped.append(topics.reassign_period(topic.id, open_period.id, client_id))
            continue
        period = period_repository.get_period(topic.period_id) if topic.period_id else None
        # Legacy rows predating per-building periods have client_id NULL.
        if period is not None and period.client_id is None:
            period_repository.assign_client(period.id, client_id)
            scoped.append(topics.reassign_period(topic.id, open_period.id, client_id))
            continue
        if topic.period_id is None:
            scoped.append(topics.reassign_period(topic.id, open_period.id, client_id))
    return scoped
