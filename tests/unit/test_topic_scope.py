"""Unit tests: committee and owner of the same building see the same topics."""

from app.domain.periods import PERIOD_STATUS_CLOSED, PeriodRecord
from app.services.topic_scope import list_topics_for_building
from app.services.topic_service import TopicService, ensure_topic_statuses
from tests.support.memory_period_repository import InMemoryPeriodRepository
from tests.support.memory_topic_repository import InMemoryTopicRepository


def _setup() -> tuple[TopicService, InMemoryPeriodRepository, InMemoryTopicRepository]:
    repository = InMemoryTopicRepository()
    ensure_topic_statuses(repository)
    return TopicService(repository), InMemoryPeriodRepository(), repository


def _create(service: TopicService, title: str, **extra):
    return service.create_topic(
        title=title,
        description="Detalle.",
        category_key="security",
        attachment_name="",
        decision="¿Lo hacemos?",
        **extra,
    )


def test_two_actors_with_same_client_id_see_the_created_topic() -> None:
    service, periods, _ = _setup()
    from app.services.period_service import PeriodService

    open_period = PeriodService(periods).ensure_current_month_open("client-1")
    created = _create(service, "Luminarias", client_id="client-1", period_id=open_period.id)

    committee_view = list_topics_for_building(service, periods, client_id="client-1")
    owner_view = list_topics_for_building(service, periods, client_id="client-1")

    assert [topic.id for topic in committee_view] == [created.id]
    assert [topic.id for topic in owner_view] == [created.id]
    assert created.client_id == "client-1"


def test_other_buildings_do_not_see_the_topic() -> None:
    service, periods, _ = _setup()
    from app.services.period_service import PeriodService

    open_period = PeriodService(periods).ensure_current_month_open("client-1")
    _create(service, "Luminarias", client_id="client-1", period_id=open_period.id)

    assert list_topics_for_building(service, periods, client_id="client-2") == []


def test_topic_with_building_but_stale_period_is_reclaimed_for_everyone() -> None:
    service, periods, repository = _setup()
    from app.services.period_service import PeriodService

    old = periods.create_period(
        PeriodRecord(id="old", name="2020-01", status=PERIOD_STATUS_CLOSED, client_id="client-1"),
    )
    open_period = PeriodService(periods).ensure_current_month_open("client-1")
    created = _create(service, "Portón", client_id="client-1", period_id=old.id)

    shown = list_topics_for_building(service, periods, client_id="client-1")

    assert [topic.id for topic in shown] == [created.id]
    assert repository.get_topic(created.id).period_id == open_period.id


def test_legacy_topic_without_client_id_is_stamped_with_the_building() -> None:
    service, periods, repository = _setup()
    from app.services.period_service import PeriodService

    open_period = PeriodService(periods).ensure_current_month_open("client-1")
    legacy = _create(service, "Antiguo", period_id=open_period.id)
    assert legacy.client_id is None

    shown = list_topics_for_building(service, periods, client_id="client-1")

    assert [topic.id for topic in shown] == [legacy.id]
    assert repository.get_topic(legacy.id).client_id == "client-1"
