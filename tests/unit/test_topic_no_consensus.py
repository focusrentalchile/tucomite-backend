"""No-consensus rules based on full turnout or voting_ends_at."""

from datetime import datetime, timezone

from app.domain.topics import (
    WAITING_STATUS_ID,
    TopicRecord,
    TopicVoteRecord,
    ensure_voting_open,
    is_no_consensus,
)


def _topic(**overrides) -> TopicRecord:
    base = TopicRecord(
        id="t1",
        title="Jardín",
        description="Entrada",
        category_key="maintenance",
        attachment_name="",
        decision="¿Qué cotización?",
        status_id=WAITING_STATUS_ID,
        priority_id=2,
        voting_ends_at="2026-11-10T12:00:00+00:00",
    )
    return TopicRecord(**{**base.__dict__, **overrides})


def test_is_no_consensus_when_everyone_voted_without_majority() -> None:
    topic = _topic()
    votes = [
        TopicVoteRecord(id="v1", topic_id="t1", author_id="u1", author_name="A", choice="yes"),
        TopicVoteRecord(id="v2", topic_id="t1", author_id="u2", author_name="B", choice="no"),
        TopicVoteRecord(id="v3", topic_id="t1", author_id="u3", author_name="C", choice="abstain"),
    ]
    before_deadline = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    assert is_no_consensus(topic, votes, committee_size=3, now=before_deadline) is True


def test_is_no_consensus_false_while_votes_missing_before_deadline() -> None:
    topic = _topic()
    votes = [
        TopicVoteRecord(id="v1", topic_id="t1", author_id="u1", author_name="A", choice="yes"),
    ]
    before_deadline = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    assert is_no_consensus(topic, votes, committee_size=3, now=before_deadline) is False


def test_is_no_consensus_after_voting_ends_without_majority() -> None:
    topic = _topic()
    votes = [
        TopicVoteRecord(id="v1", topic_id="t1", author_id="u1", author_name="A", choice="yes"),
    ]
    after_deadline = datetime(2026, 11, 10, 12, 0, 1, tzinfo=timezone.utc)
    assert is_no_consensus(topic, votes, committee_size=3, now=after_deadline) is True


def test_is_no_consensus_false_when_majority_exists() -> None:
    topic = _topic()
    votes = [
        TopicVoteRecord(id="v1", topic_id="t1", author_id="u1", author_name="A", choice="yes"),
        TopicVoteRecord(id="v2", topic_id="t1", author_id="u2", author_name="B", choice="yes"),
        TopicVoteRecord(id="v3", topic_id="t1", author_id="u3", author_name="C", choice="no"),
    ]
    after_deadline = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
    assert is_no_consensus(topic, votes, committee_size=3, now=after_deadline) is False


def test_voting_stays_open_until_voting_ends_at() -> None:
    topic = _topic()
    ensure_voting_open(topic, datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc))


def test_voting_stays_open_after_voting_ends_at_while_waiting() -> None:
    topic = _topic()
    ensure_voting_open(topic, datetime(2026, 11, 10, 12, 0, 1, tzinfo=timezone.utc))
