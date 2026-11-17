from app.domain.topics import execution_quorum_met
from app.services.topic_service import _winning_vote_count
from app.domain.topics import TopicRecord, TopicVoteOptionRecord, TopicVoteRecord, VOTE_TYPE_CUSTOM, VOTE_TYPE_YES_NO


def test_execution_quorum_requires_strict_majority() -> None:
    assert execution_quorum_met(2, 3) is True
    assert execution_quorum_met(1, 3) is False
    assert execution_quorum_met(0, 0) is False


def test_winning_vote_count_yes_no_and_custom() -> None:
    topic = TopicRecord(
        id="t1",
        title="T",
        description="D",
        category_key="other",
        attachment_name="",
        decision="?",
        status_id=2,
        priority_id=2,
        vote_type=VOTE_TYPE_YES_NO,
    )
    votes = [
        TopicVoteRecord(id="1", topic_id="t1", author_id="a", author_name="A", choice="yes"),
        TopicVoteRecord(id="2", topic_id="t1", author_id="b", author_name="B", choice="no"),
        TopicVoteRecord(id="3", topic_id="t1", author_id="c", author_name="C", choice="yes"),
    ]
    assert _winning_vote_count(topic, votes) == 2

    custom = TopicRecord(
        id="t2",
        title="T",
        description="D",
        category_key="other",
        attachment_name="",
        decision="?",
        status_id=2,
        priority_id=2,
        vote_type=VOTE_TYPE_CUSTOM,
        vote_options=(
            TopicVoteOptionRecord(id="opt-a", label="A"),
            TopicVoteOptionRecord(id="opt-b", label="B"),
        ),
    )
    custom_votes = [
        TopicVoteRecord(id="1", topic_id="t2", author_id="a", author_name="A", choice="opt-a"),
        TopicVoteRecord(id="2", topic_id="t2", author_id="b", author_name="B", choice="opt-a"),
        TopicVoteRecord(id="3", topic_id="t2", author_id="c", author_name="C", choice="opt-b"),
    ]
    assert _winning_vote_count(custom, custom_votes) == 2
