"""Unit tests for new-opinion notices, unread counts, and the assign-ready alert."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import app.services.topic_notification_email as topic_mail
from app.api.v1.endpoints.topics import unread_opinion_count_for
from app.domain.email_templates import (
    EMAIL_TEMPLATE_KEYS,
    TEMPLATE_TOPIC_ASSIGN_READY,
    TEMPLATE_TOPIC_OPINION,
)
from app.domain.topics import (
    DOING_STATUS_ID,
    OPEN_STATUS_ID,
    WAITING_STATUS_ID,
    TopicOpinionRecord,
    TopicRecord,
    TopicVoteRecord,
    is_assign_ready,
)
from app.services.email_template_defaults import DEFAULT_TEMPLATES
from app.services.topic_service import TopicService
from tests.support.memory_topic_repository import InMemoryTopicRepository


def _topic(*, status_id: int = WAITING_STATUS_ID, assignee: str | None = None) -> TopicRecord:
    return TopicRecord(
        id="topic-1",
        title="Ascensor",
        description="No sube.",
        category_key="maintenance",
        attachment_name="",
        decision="¿Reparamos?",
        status_id=status_id,
        priority_id=2,
        assignee_user_id=assignee,
        client_id="client-1",
    )


def _vote(index: int, choice: str = "yes") -> TopicVoteRecord:
    return TopicVoteRecord(
        id=f"vote-{index}",
        topic_id="topic-1",
        author_id=f"user-{index}",
        author_name=f"Persona {index}",
        choice=choice,
    )


def _opinion(author_id: str, created_at: str) -> TopicOpinionRecord:
    return TopicOpinionRecord(
        id=f"op-{author_id}-{created_at}",
        topic_id="topic-1",
        author_id=author_id,
        author_name=author_id,
        body="Opino que sí.",
        created_at=created_at,
    )


def test_assign_ready_email_template_is_registered_with_defaults() -> None:
    assert TEMPLATE_TOPIC_ASSIGN_READY == "topic_assign_ready"
    assert TEMPLATE_TOPIC_ASSIGN_READY in EMAIL_TEMPLATE_KEYS
    defaults = DEFAULT_TEMPLATES[TEMPLATE_TOPIC_ASSIGN_READY]
    assert "ya tiene los votos para asignar" in defaults["subject"]
    assert "{{topic_title}}" in defaults["subject"]
    assert "{{topic_url}}" in defaults["html_body"]
    assert "puedes" in defaults["html_body"]


def test_topic_opinion_email_template_is_registered_with_defaults() -> None:
    assert TEMPLATE_TOPIC_OPINION == "topic_opinion"
    assert TEMPLATE_TOPIC_OPINION in EMAIL_TEMPLATE_KEYS
    defaults = DEFAULT_TEMPLATES[TEMPLATE_TOPIC_OPINION]
    assert "debate" in defaults["subject"].casefold()
    assert "{{actor_name}}" in defaults["html_body"]
    assert "{{topic_url}}" in defaults["html_body"]
    assert "Abre el tema" in defaults["html_body"]


def test_is_assign_ready_needs_waiting_majority_and_no_assignee() -> None:
    votes = [_vote(1), _vote(2)]
    assert is_assign_ready(_topic(), votes, committee_size=3) is True
    assert is_assign_ready(_topic(), [_vote(1)], committee_size=3) is False
    assert is_assign_ready(_topic(status_id=OPEN_STATUS_ID), votes, committee_size=3) is False
    assert is_assign_ready(_topic(status_id=DOING_STATUS_ID), votes, committee_size=3) is False
    assert is_assign_ready(_topic(assignee="user-9"), votes, committee_size=3) is False


def test_unread_opinion_count_skips_own_and_seen_opinions() -> None:
    opinions = [
        _opinion("me", "2026-11-17T10:00:00"),
        _opinion("ana", "2026-11-17T10:05:00"),
        _opinion("luis", "2026-11-17T10:30:00.250000"),
    ]
    assert unread_opinion_count_for(opinions, actor_id="me", last_seen_at=None) == 2
    assert (
        unread_opinion_count_for(opinions, actor_id="me", last_seen_at="2026-11-17T10:10:00") == 1
    )
    assert (
        unread_opinion_count_for(opinions, actor_id="me", last_seen_at="2026-11-17T11:00:00") == 0
    )


def test_mark_opinions_seen_stores_and_lists_the_instant() -> None:
    repository = InMemoryTopicRepository()
    service = TopicService(repository)
    topic = service.create_topic("Ascensor", "No sube.", "maintenance", "", "¿Reparamos?")
    assert service.list_opinion_reads("user-1", [topic.id]) == {}
    seen_at = service.mark_opinions_seen(topic.id, "user-1")
    assert service.list_opinion_reads("user-1", [topic.id]) == {topic.id: seen_at}
    assert service.list_opinion_reads("user-2", [topic.id]) == {}


def test_notify_topic_opinion_skips_the_author_and_emails_only_on_first() -> None:
    added: list[dict] = []

    def fake_add(db, **kwargs):  # noqa: ANN001, ANN003
        added.append(kwargs)
        return len(kwargs["user_ids"])

    author = MagicMock()
    author.email = "ana@example.com"
    access = MagicMock()
    access.get_user.return_value = author

    with (
        patch.object(
            topic_mail,
            "_voter_and_owner_user_ids",
            return_value=["author", "voter-1", "owner-1"],
        ),
        patch.object(topic_mail, "_add_in_app_notices", side_effect=fake_add),
        patch.object(topic_mail, "SqlAccessRepository", return_value=access),
        patch.object(topic_mail, "_send_to_committee", return_value=2) as send,
    ):
        later = topic_mail.notify_topic_opinion(
            MagicMock(),
            topic=_topic(),
            author_id="author",
            author_name="Ana",
            client_id="client-1",
            send_email=False,
        )
        first = topic_mail.notify_topic_opinion(
            MagicMock(),
            topic=_topic(),
            author_id="author",
            author_name="Ana",
            client_id="client-1",
            send_email=True,
        )

    assert later == 2
    assert first == 4
    assert added[0]["title"] == "Nueva opinión"
    assert added[1]["title"] == "Se inició el debate"
    assert added[1]["user_ids"] == ["voter-1", "owner-1"]
    assert added[1]["kind"] == "topic_opinion"
    assert "Ana" in added[1]["body"]
    assert "Ascensor" in added[1]["body"]
    assert send.call_count == 1
    assert send.call_args.kwargs["template_key"] == TEMPLATE_TOPIC_OPINION
    assert send.call_args.kwargs["exclude_emails"] == {"ana@example.com"}


def test_notify_topic_assign_ready_sends_notice_and_template_email() -> None:
    added: list[dict] = []
    with (
        patch.object(topic_mail, "_building_name", return_value="Edificio Norte"),
        patch.object(topic_mail, "_voter_and_owner_user_ids", return_value=["u1", "owner-1"]),
        patch.object(
            topic_mail,
            "_add_in_app_notices",
            side_effect=lambda db, **kwargs: added.append(kwargs) or 2,
        ),
        patch.object(topic_mail, "_send_to_committee", return_value=3) as send,
    ):
        sent = topic_mail.notify_topic_assign_ready(
            MagicMock(),
            topic=_topic(),
            client_id="client-1",
            actor_name="Ana",
        )

    assert sent == 3
    assert added[0]["kind"] == "topic_assign_ready"
    assert added[0]["user_ids"] == ["u1", "owner-1"]
    assert send.call_args.kwargs["template_key"] == TEMPLATE_TOPIC_ASSIGN_READY
