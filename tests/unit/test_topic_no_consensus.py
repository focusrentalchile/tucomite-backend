"""No-consensus grace window after voting ends without a majority."""

from datetime import datetime, timedelta, timezone

from app.domain.topics import (
    WAITING_STATUS_ID,
    TopicRecord,
    TopicVoteRecord,
    VotingWindowClosed,
    consensus_grace_ends_at,
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


def test_is_no_consensus_when_voting_ended_without_majority() -> None:
    topic = _topic()
    votes = [
        TopicVoteRecord(id="v1", topic_id="t1", author_id="u1", author_name="A", choice="yes"),
    ]
    now = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
    assert is_no_consensus(topic, votes, committee_size=3, now=now) is True


def test_consensus_grace_keeps_voting_open_for_five_days() -> None:
    topic = _topic()
    votes = [
        TopicVoteRecord(id="v1", topic_id="t1", author_id="u1", author_name="A", choice="yes"),
    ]
    grace = consensus_grace_ends_at(topic)
    assert grace is not None
    assert grace == datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc) + timedelta(days=5)
    ensure_voting_open(
        topic,
        datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc),
        votes=votes,
        committee_size=3,
    )


def test_voting_locks_after_consensus_grace() -> None:
    topic = _topic()
    votes = [
        TopicVoteRecord(id="v1", topic_id="t1", author_id="u1", author_name="A", choice="yes"),
    ]
    try:
        ensure_voting_open(
            topic,
            datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc),
            votes=votes,
            committee_size=3,
        )
        raise AssertionError("expected VotingWindowClosed")
    except VotingWindowClosed as error:
        assert error.reason == "ended"
