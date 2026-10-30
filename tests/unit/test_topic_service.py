"""Unit tests for the status table, new topics, and votes."""



from app.domain.topics import (
    OPEN_STATUS_ID,
    TOPIC_STATUSES,
    WAITING_STATUS_ID,
    TopicNotFound,
    VoteAlreadyCast,
)

from app.services.topic_service import TopicService, ensure_topic_statuses

from tests.support.memory_topic_repository import InMemoryTopicRepository





def test_status_table_uses_stable_ids_for_each_board_column() -> None:

    repository = InMemoryTopicRepository()



    ensure_topic_statuses(repository)

    ensure_topic_statuses(repository)



    assert [(status.id, status.key) for status in repository.list_statuses()] == list(TOPIC_STATUSES)





def test_new_topic_starts_in_the_open_status() -> None:

    repository = InMemoryTopicRepository()

    ensure_topic_statuses(repository)

    service = TopicService(repository)



    topic = service.create_topic(

        title="Luminarias",

        description="Están apagadas.",

        category_key="security",

        attachment_name="",

        decision="¿Pedimos cotizaciones?",

    )



    assert topic.status_id == OPEN_STATUS_ID

    assert topic.status_id == 1

    assert repository.list_topics()[0].status_id == 1





def test_first_vote_is_stored_and_moves_topic_to_waiting() -> None:

    repository = InMemoryTopicRepository()

    ensure_topic_statuses(repository)

    service = TopicService(repository)

    topic = service.create_topic(

        title="Luminarias",

        description="Están apagadas.",

        category_key="security",

        attachment_name="",

        decision="¿Pedimos cotizaciones?",

    )



    updated, vote = service.cast_vote(

        topic.id,

        author_id="user-1",

        author_name="Ana Pérez",

        choice="yes",

    )



    assert vote.choice == "yes"

    assert vote.author_name == "Ana Pérez"

    assert updated.status_id == WAITING_STATUS_ID

    assert repository.get_topic(topic.id) is not None

    assert repository.get_topic(topic.id).status_id == WAITING_STATUS_ID

    assert repository.list_votes(topic.id) == [vote]





def test_same_author_cannot_change_or_repeat_a_vote() -> None:

    repository = InMemoryTopicRepository()

    ensure_topic_statuses(repository)

    service = TopicService(repository)

    topic = service.create_topic(

        title="Luminarias",

        description="Están apagadas.",

        category_key="security",

        attachment_name="",

        decision="¿Pedimos cotizaciones?",

    )

    first, vote = service.cast_vote(topic.id, "user-1", "Ana Pérez", "yes")



    try:

        service.cast_vote(topic.id, "user-1", "Ana Pérez", "no")

        raised = False

    except VoteAlreadyCast:

        raised = True



    assert raised

    assert vote.choice == "yes"

    assert len(repository.list_votes(topic.id)) == 1

    assert first.status_id == WAITING_STATUS_ID

    assert repository.list_votes(topic.id)[0].choice == "yes"





def test_abstain_vote_is_stored() -> None:

    repository = InMemoryTopicRepository()

    ensure_topic_statuses(repository)

    service = TopicService(repository)

    topic = service.create_topic(

        title="Luminarias",

        description="Están apagadas.",

        category_key="security",

        attachment_name="",

        decision="¿Pedimos cotizaciones?",

    )



    updated, vote = service.cast_vote(topic.id, "user-2", "Luis Soto", "abstain")



    assert vote.choice == "abstain"

    assert updated.status_id == WAITING_STATUS_ID

    assert repository.list_votes(topic.id)[0].choice == "abstain"





def test_vote_on_missing_topic_raises() -> None:

    service = TopicService(InMemoryTopicRepository())



    try:

        service.cast_vote("missing", "user-1", "Ana", "yes")

        raised = False

    except TopicNotFound:

        raised = True



    assert raised





def test_upsert_opinion_creates_and_updates() -> None:
    repository = InMemoryTopicRepository()
    ensure_topic_statuses(repository)
    service = TopicService(repository)
    topic = service.create_topic(
        title="Luminarias",
        description="Están apagadas.",
        category_key="security",
        attachment_name="",
        decision="¿Pedimos cotizaciones?",
    )

    first = service.upsert_opinion(topic.id, "user-1", "Ana Pérez", "Hay que cotizar")
    second = service.upsert_opinion(topic.id, "user-2", "Luis Soto", "Mejor esperar")
    updated = service.upsert_opinion(topic.id, "user-1", "Ana Pérez", "Cotizar ya")

    listed = service.list_opinions_for_topics([topic.id])
    assert len(listed) == 2
    assert first.id == updated.id
    assert updated.body == "Cotizar ya"
    assert {item.author_id for item in listed} == {"user-1", "user-2"}
    assert second.body == "Mejor esperar"


def test_update_move_and_delete_topic_persist() -> None:

    repository = InMemoryTopicRepository()

    ensure_topic_statuses(repository)

    service = TopicService(repository)

    topic = service.create_topic(

        title="Luminarias",

        description="Están apagadas.",

        category_key="security",

        attachment_name="",

        decision="¿Pedimos cotizaciones?",

    )



    updated = service.update_topic(

        topic.id,

        title="Luminarias nuevas",

        description="Hay que cambiarlas.",

        category_key="maintenance",

        attachment_name="foto.png",

        decision="¿Compramos ya?",

    )

    moved = service.move_topic(topic.id, 3)



    assert updated.title == "Luminarias nuevas"

    assert updated.category_key == "maintenance"

    assert moved.status_id == 3

    assert repository.get_topic(topic.id).status_id == 3



    service.delete_topic(topic.id)



    assert repository.get_topic(topic.id) is None

