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

    assert vote.choice == "yes"
    assert first.status_id == WAITING_STATUS_ID

    # While waiting for a decision, the same voter may change their choice.
    changed_topic, changed = service.cast_vote(topic.id, "user-1", "Ana Pérez", "no")
    assert changed.choice == "no"
    assert changed_topic.status_id == WAITING_STATUS_ID
    assert len(repository.list_votes(topic.id)) == 1
    assert repository.list_votes(topic.id)[0].choice == "no"

    # After leaving the waiting column, the vote is locked again.
    repository.save_topic_status(topic.id, 3)
    try:
        service.cast_vote(topic.id, "user-1", "Ana Pérez", "abstain")
        raised = False
    except VoteAlreadyCast:
        raised = True
    assert raised





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





def test_create_topic_stores_attachments() -> None:
    repository = InMemoryTopicRepository()
    ensure_topic_statuses(repository)
    service = TopicService(repository)

    topic = service.create_topic(
        title="Luminarias",
        description="Están apagadas.",
        category_key="security",
        attachment_name="luz.png",
        decision="¿Pedimos cotizaciones?",
        attachments=[
            {"kind": "image", "name": "luz.png", "url": "data:image/png;base64,aaa"},
            {"kind": "file", "name": "nota.pdf", "url": "data:application/pdf;base64,bbb"},
        ],
    )

    stored = service.list_attachments_for_topics([topic.id])
    assert len(stored) == 2
    assert {item.kind for item in stored} == {"image", "file"}


def test_delete_own_opinion() -> None:
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
    first = service.create_opinion(topic.id, "user-1", "Ana Pérez", "Hay que cotizar")
    service.create_opinion(topic.id, "user-2", "Luis Soto", "Mejor esperar")
    service.delete_opinion(topic.id, first.id, "user-1")
    listed = service.list_opinions_for_topics([topic.id])
    assert len(listed) == 1
    assert listed[0].author_id == "user-2"


def test_create_opinion_appends_many_per_author() -> None:
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

    first = service.create_opinion(topic.id, "user-1", "Ana Pérez", "Hay que cotizar")
    second = service.create_opinion(topic.id, "user-2", "Luis Soto", "Mejor esperar")
    third = service.create_opinion(topic.id, "user-1", "Ana Pérez", "Cotizar ya")

    listed = service.list_opinions_for_topics([topic.id])
    assert len(listed) == 3
    assert first.id != third.id
    assert third.body == "Cotizar ya"
    assert {item.author_id for item in listed} == {"user-1", "user-2"}
    assert second.body == "Mejor esperar"
    assert [item.body for item in listed] == ["Hay que cotizar", "Mejor esperar", "Cotizar ya"]


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

    repository.save_topic_status(topic.id, 3)
    moved = repository.get_topic(topic.id)

    assert updated.title == "Luminarias nuevas"

    assert updated.category_key == "maintenance"

    assert moved is not None and moved.status_id == 3

    assert repository.get_topic(topic.id).status_id == 3



    service.delete_topic(topic.id)



    assert repository.get_topic(topic.id) is None


def test_completion_and_confirmations_gate_close() -> None:
    from app.domain.topics import (
        CompletionNotSubmitted,
        CompletionQuorumNotMet,
        ConfirmationAlreadyCast,
    )

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
    repository.save_topic_status(topic.id, 3)

    try:
        service.move_topic(topic.id, 4, committee_size=3)
        raise AssertionError("expected CompletionNotSubmitted")
    except CompletionNotSubmitted:
        pass

    completed = service.submit_completion(
        topic.id,
        note="Ya se cambió la luminaria.",
        attachments=[{"kind": "image", "name": "foto.jpg", "url": "data:image/jpeg;base64,abc"}],
    )
    assert completed.completion_note == "Ya se cambió la luminaria."
    assert completed.completion_submitted_at
    assert len(repository.list_completion_attachments_for_topics([topic.id])) == 1

    try:
        service.move_topic(topic.id, 4, committee_size=3)
        raise AssertionError("expected CompletionQuorumNotMet")
    except CompletionQuorumNotMet:
        pass

    service.confirm_completion(topic.id, "user-1", "Ana", choice="yes")
    service.confirm_completion(
        topic.id,
        "user-3",
        "Marta",
        choice="no",
        reason="Falta pintar el marco.",
    )
    service.confirm_completion(topic.id, "user-2", "Luis", choice="yes")
    try:
        service.confirm_completion(topic.id, "user-1", "Ana", choice="yes")
        raise AssertionError("expected ConfirmationAlreadyCast")
    except ConfirmationAlreadyCast:
        pass

    closed = service.move_topic(topic.id, 4, committee_size=3)
    assert closed.status_id == 4


def test_resultado_second_no_seals_even_with_autoflush_disabled_pattern() -> None:
    """The second No must seal using the vote just stored (session may not autoflush)."""
    repository = InMemoryTopicRepository()
    ensure_topic_statuses(repository)
    service = TopicService(repository)
    topic = service.create_topic(
        title="Ascensor",
        description="No sube.",
        category_key="maintenance",
        attachment_name="",
        decision="¿Reparamos?",
    )
    repository.save_topic_status(topic.id, 3)
    service.submit_completion(topic.id, note="Primera entrega")
    service.confirm_completion(
        topic.id, "user-1", "Ana", choice="no", reason="Falta 1", committee_size=3,
    )
    sealed = service.confirm_completion(
        topic.id, "user-2", "Luis", choice="no", reason="Falta 2", committee_size=3,
    )[0]
    assert sealed.completion_submitted_at is None
    assert sealed.completion_round == 2
    assert len(sealed.completion_rounds) == 1
    assert sealed.completion_rounds[0].confirmations[-1].reason == "Falta 2"


def test_seal_failed_completion_if_needed_heals_open_no_majority() -> None:
    repository = InMemoryTopicRepository()
    ensure_topic_statuses(repository)
    service = TopicService(repository)
    topic = service.create_topic(
        title="Ascensor",
        description="No sube.",
        category_key="maintenance",
        attachment_name="",
        decision="¿Reparamos?",
    )
    repository.save_topic_status(topic.id, 3)
    service.submit_completion(topic.id, note="Se cambió el motor.")
    service.confirm_completion(topic.id, "user-1", "Ana", choice="no", reason="Falta pintura.", committee_size=0)
    service.confirm_completion(topic.id, "user-2", "Luis", choice="no", reason="Sigue ruidoso.", committee_size=0)
    open_topic = repository.get_topic(topic.id)
    assert open_topic is not None
    assert open_topic.completion_submitted_at is not None
    healed = service.seal_failed_completion_if_needed(open_topic, committee_size=3)
    assert healed.completion_submitted_at is None
    assert healed.completion_round == 2
    assert len(healed.completion_rounds) == 1
    assert healed.completion_rounds[0].confirmations[0].reason == "Falta pintura."


def test_resultado_no_majority_seals_round_and_allows_new_completion() -> None:
    repository = InMemoryTopicRepository()
    ensure_topic_statuses(repository)
    service = TopicService(repository)
    topic = service.create_topic(
        title="Ascensor",
        description="No sube.",
        category_key="maintenance",
        attachment_name="",
        decision="¿Reparamos?",
    )
    repository.save_topic_status(topic.id, 3)
    service.submit_completion(topic.id, note="Se cambió el motor.")
    service.confirm_completion(topic.id, "user-1", "Ana", choice="no", reason="Falta pintura.", committee_size=3)
    service.confirm_completion(topic.id, "user-2", "Luis", choice="no", reason="Sigue ruidoso.", committee_size=3)
    refreshed = repository.get_topic(topic.id)
    assert refreshed is not None
    assert refreshed.completion_submitted_at is None
    assert refreshed.completion_round == 2
    assert len(refreshed.completion_rounds) == 1
    assert refreshed.completion_rounds[0].outcome == "failed"
    assert repository.list_confirmations_for_topics([topic.id]) == []
    again = service.submit_completion(topic.id, note="Segunda entrega con pintura.")
    assert again.completion_submitted_at is not None
    assert again.completion_note == "Segunda entrega con pintura."


def test_resultado_no_requires_reason() -> None:
    repository = InMemoryTopicRepository()
    ensure_topic_statuses(repository)
    service = TopicService(repository)
    topic = service.create_topic(
        title="Ascensor",
        description="No sube.",
        category_key="maintenance",
        attachment_name="",
        decision="¿Reparamos?",
    )
    repository.save_topic_status(topic.id, 3)
    service.submit_completion(topic.id, note="Se cambió el motor.")
    try:
        service.confirm_completion(topic.id, "user-1", "Ana", choice="no", reason="")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    _, vote = service.confirm_completion(
        topic.id,
        "user-1",
        "Ana",
        choice="no",
        reason="Sigue fallando el sensor.",
    )
    assert vote.choice == "no"
    assert vote.reason == "Sigue fallando el sensor."


def test_custom_poll_stores_options_and_accepts_option_votes() -> None:
    from app.domain.topics import InvalidVoteChoice, VOTE_TYPE_CUSTOM

    repository = InMemoryTopicRepository()
    ensure_topic_statuses(repository)
    service = TopicService(repository)

    topic = service.create_topic(
        title="Pintura",
        description="Hay que elegir color.",
        category_key="maintenance",
        attachment_name="",
        decision="¿Qué color pintamos el hall?",
        vote_type=VOTE_TYPE_CUSTOM,
        vote_options=[
            {"id": "opt-blue", "label": "Azul"},
            {"id": "opt-green", "label": "Verde"},
            {"label": "Blanco"},
        ],
    )

    assert topic.vote_type == VOTE_TYPE_CUSTOM
    assert [option.label for option in topic.vote_options] == ["Azul", "Verde", "Blanco"]
    assert topic.vote_options[0].id == "opt-blue"

    updated, vote = service.cast_vote(
        topic.id,
        author_id="user-1",
        author_name="Ana",
        choice="opt-green",
    )
    assert vote.choice == "opt-green"
    assert updated.status_id == WAITING_STATUS_ID
    assert repository.get_topic(topic.id).vote_options[1].label == "Verde"

    try:
        service.cast_vote(topic.id, author_id="user-2", author_name="Luis", choice="yes")
        raise AssertionError("expected InvalidVoteChoice")
    except InvalidVoteChoice:
        pass


def test_yes_no_poll_rejects_custom_option_ids() -> None:
    from app.domain.topics import InvalidVoteChoice

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

    try:
        service.cast_vote(topic.id, author_id="user-1", author_name="Ana", choice="opt-x")
        raise AssertionError("expected InvalidVoteChoice")
    except InvalidVoteChoice:
        pass

