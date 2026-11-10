"""Unit tests for the voting window on topics."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.topics import InvalidVotingWindow, VotingWindowClosed
from app.services.topic_service import TopicService, ensure_topic_statuses
from tests.support.memory_topic_repository import InMemoryTopicRepository

START = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
END = START + timedelta(hours=24)


def _service() -> TopicService:
    repository = InMemoryTopicRepository()
    ensure_topic_statuses(repository)
    return TopicService(repository)


def _create(service: TopicService, **extra):
    return service.create_topic(
        title="Luminarias",
        description="Están apagadas.",
        category_key="security",
        attachment_name="",
        decision="¿Pedimos cotizaciones?",
        **extra,
    )


def test_create_topic_stores_the_voting_window_dates() -> None:
    service = _service()

    topic = _create(
        service,
        voting_starts_at="2026-11-10T12:00:00Z",
        voting_ends_at="2026-11-11T12:00:00-00:00",
    )

    assert topic.voting_starts_at == START.isoformat()
    assert topic.voting_ends_at == END.isoformat()


def test_create_topic_without_dates_has_no_window() -> None:
    topic = _create(_service())

    assert topic.voting_starts_at is None
    assert topic.voting_ends_at is None


def test_default_hours_close_the_window_when_no_end_is_given() -> None:
    service = _service()

    topic = _create(service, voting_starts_at="2026-11-10T12:00:00Z", default_window_hours=72)

    assert topic.voting_ends_at == (START + timedelta(hours=72)).isoformat()


def test_explicit_end_wins_over_default_hours() -> None:
    topic = _create(
        _service(),
        voting_starts_at="2026-11-10T12:00:00Z",
        voting_ends_at="2026-11-11T12:00:00Z",
        default_window_hours=168,
    )

    assert topic.voting_ends_at == END.isoformat()


def test_window_must_end_after_it_starts() -> None:
    with pytest.raises(InvalidVotingWindow):
        _create(
            _service(),
            voting_starts_at="2026-11-11T12:00:00Z",
            voting_ends_at="2026-11-10T12:00:00Z",
        )


def test_window_rejects_invalid_dates() -> None:
    with pytest.raises(InvalidVotingWindow):
        _create(_service(), voting_starts_at="mañana")


def test_vote_inside_the_window_is_accepted() -> None:
    service = _service()
    topic = _create(service, voting_starts_at=START.isoformat(), voting_ends_at=END.isoformat())

    _, vote = service.cast_vote(topic.id, "user-1", "Ana", "yes", now=START + timedelta(hours=1))

    assert vote.choice == "yes"


def test_vote_before_the_window_is_rejected() -> None:
    service = _service()
    topic = _create(service, voting_starts_at=START.isoformat(), voting_ends_at=END.isoformat())

    with pytest.raises(VotingWindowClosed) as raised:
        service.cast_vote(topic.id, "user-1", "Ana", "yes", now=START - timedelta(minutes=1))

    assert raised.value.reason == "not_started"


def test_vote_after_the_window_is_rejected_and_locks_changes() -> None:
    service = _service()
    topic = _create(service, voting_starts_at=START.isoformat(), voting_ends_at=END.isoformat())
    service.cast_vote(topic.id, "user-1", "Ana", "yes", now=START + timedelta(hours=1))

    with pytest.raises(VotingWindowClosed) as raised:
        service.cast_vote(topic.id, "user-1", "Ana", "no", now=END + timedelta(seconds=1))

    assert raised.value.reason == "ended"
    assert service.list_votes_for_topics([topic.id])[0].choice == "yes"


def test_topic_without_window_never_locks() -> None:
    service = _service()
    topic = _create(service)

    _, vote = service.cast_vote(topic.id, "user-1", "Ana", "yes", now=START + timedelta(days=3650))

    assert vote.choice == "yes"
