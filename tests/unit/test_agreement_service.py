"""Unit tests for publishing agreements from closed topics."""

from app.domain.topics import CLOSED_STATUS_ID, OPEN_STATUS_ID, TopicOpinionRecord, TopicRecord, TopicVoteRecord
from app.services.agreement_service import AgreementService
from tests.support.memory_agreement_repository import InMemoryAgreementRepository


class _Topics:
    def __init__(self) -> None:
        self.topic = TopicRecord(
            id="t1",
            title="Cámaras",
            description="Seguridad del patio.",
            category_key="security",
            attachment_name="",
            decision="¿Instalamos cámaras?",
            status_id=CLOSED_STATUS_ID,
            priority_id=2,
            closed_at="2026-03-01T12:00:00",
            period_id="p1",
        )
        self.votes = [
            TopicVoteRecord(id="v1", topic_id="t1", author_id="u1", author_name="Ana", choice="yes"),
            TopicVoteRecord(id="v2", topic_id="t1", author_id="u2", author_name="Luis", choice="yes"),
            TopicVoteRecord(id="v3", topic_id="t1", author_id="u3", author_name="Marta", choice="no"),
        ]
        self.opinions = [
            TopicOpinionRecord(
                id="o1",
                topic_id="t1",
                author_id="u1",
                author_name="Ana",
                body="Hay que hacerlo.",
                created_at="2026-02-01T10:00:00",
            ),
        ]

    def get_topic(self, topic_id: str):
        return self.topic if topic_id == self.topic.id else None

    def list_topics(self):
        return [self.topic]

    def list_votes_for_topics(self, topic_ids: list[str]):
        return [vote for vote in self.votes if vote.topic_id in topic_ids]

    def list_opinions_for_topics(self, topic_ids: list[str]):
        return [item for item in self.opinions if item.topic_id in topic_ids]


def test_publish_from_closed_topic_creates_pdf_once() -> None:
    agreements = InMemoryAgreementRepository()
    topics = _Topics()
    service = AgreementService(agreements, topics)

    first = service.publish_from_topic("t1", client_id="c1")
    second = service.publish_from_topic("t1", client_id="c1")

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert first.vote_result == "approved"
    assert first.vote_yes == 2
    assert first.vote_no == 1
    detail = agreements.get(first.id)
    assert detail is not None
    assert detail.pdf_bytes.startswith(b"%PDF")
    assert "¿Instalamos cámaras?" in first.summary


def test_open_topic_is_not_published() -> None:
    agreements = InMemoryAgreementRepository()
    topics = _Topics()
    topics.topic = TopicRecord(
        id="t1",
        title="Cámaras",
        description="Seguridad del patio.",
        category_key="security",
        attachment_name="",
        decision="¿Instalamos cámaras?",
        status_id=OPEN_STATUS_ID,
        priority_id=2,
        period_id="p1",
    )
    service = AgreementService(agreements, topics)
    assert service.publish_from_topic("t1", client_id="c1") is None
