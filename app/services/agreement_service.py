"""Publish closed topics as agreements with branded PDF actas."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.domain.agreements import (
    VOTE_RESULT_APPROVED,
    VOTE_RESULT_CUSTOM,
    VOTE_RESULT_NO_VOTES,
    VOTE_RESULT_REJECTED,
    VOTE_RESULT_TIED,
    AgreementDetailRecord,
    AgreementNotFound,
    AgreementRecord,
)
from app.domain.topics import (
    CLOSED_STATUS_ID,
    VOTE_TYPE_CUSTOM,
    TopicNotFound,
    TopicOpinionRecord,
    TopicRecord,
    TopicVoteRecord,
)
from app.repositories.agreement_repository import AgreementRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.topic_repository import TopicRepository
from app.services.agreement_pdf_service import CATEGORY_LABELS, RESULT_LABELS, build_agreement_pdf


class AgreementService:
    """Creates and lists agreements from closed topics."""

    def __init__(
        self,
        agreements: AgreementRepository,
        topics: TopicRepository,
        clients: ClientRepository | None = None,
    ) -> None:
        self._agreements = agreements
        self._topics = topics
        self._clients = clients

    def list_agreements(self, *, client_id: str | None = None) -> list[AgreementRecord]:
        """Return published agreements."""
        return self._agreements.list_agreements(client_id=client_id)

    def get_agreement(self, agreement_id: str) -> AgreementDetailRecord:
        """Return one agreement with PDF bytes."""
        record = self._agreements.get(agreement_id)
        if record is None:
            raise AgreementNotFound(agreement_id)
        return record

    def publish_from_topic(
        self,
        topic_id: str,
        *,
        client_id: str | None,
    ) -> AgreementRecord | None:
        """Create an agreement + PDF when a topic is closed. Idempotent per topic."""
        existing = self._agreements.get_by_topic(topic_id)
        if existing is not None:
            return existing

        topic = self._topics.get_topic(topic_id)
        if topic is None:
            raise TopicNotFound()
        if topic.status_id != CLOSED_STATUS_ID:
            return None

        votes = self._topics.list_votes_for_topics([topic_id])
        opinions = self._topics.list_opinions_for_topics([topic_id])
        yes_count = sum(1 for vote in votes if vote.choice == "yes")
        no_count = sum(1 for vote in votes if vote.choice == "no")
        abstain_count = sum(1 for vote in votes if vote.choice == "abstain")
        vote_choice_labels = {
            "yes": "A favor",
            "no": "En contra",
            "abstain": "Abstención",
        }
        vote_option_counts: list[tuple[str, int]] | None = None
        if topic.vote_type == VOTE_TYPE_CUSTOM:
            vote_option_counts = []
            option_lines: list[str] = []
            for option in topic.vote_options:
                count = sum(1 for vote in votes if vote.choice == option.id)
                vote_option_counts.append((option.label, count))
                option_lines.append(f"{option.label}: {count}")
                vote_choice_labels[option.id] = option.label
            option_lines.append(f"Abstenciones: {abstain_count}")
            vote_result = VOTE_RESULT_NO_VOTES if not votes else VOTE_RESULT_CUSTOM
            summary = self._summary_custom(topic, option_lines, opinions)
        else:
            vote_result = self._vote_result(yes_count, no_count, abstain_count)
            summary = self._summary(topic, yes_count, no_count, abstain_count, vote_result, opinions)
        building_name = self._building_name(client_id)
        pdf_bytes = build_agreement_pdf(
            title=topic.title,
            decision=topic.decision,
            description=topic.description,
            category_key=topic.category_key,
            vote_yes=yes_count,
            vote_no=no_count,
            vote_abstain=abstain_count,
            vote_result=vote_result,
            closed_at=topic.closed_at,
            votes=votes,
            opinions=opinions,
            building_name=building_name,
            vote_option_counts=vote_option_counts,
            vote_choice_labels=vote_choice_labels,
        )
        safe_title = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in topic.title)[:40]
        pdf_name = f"acuerdo-{safe_title or 'tema'}.pdf"
        now = datetime.now(timezone.utc).isoformat()
        record = AgreementDetailRecord(
            id=str(uuid4()),
            topic_id=topic.id,
            period_id=topic.period_id,
            client_id=client_id,
            title=topic.title,
            decision=topic.decision,
            description=topic.description,
            category_key=topic.category_key,
            summary=summary,
            vote_yes=yes_count,
            vote_no=no_count,
            vote_abstain=abstain_count,
            vote_result=vote_result,
            closed_at=topic.closed_at,
            created_at=now,
            pdf_name=pdf_name,
            pdf_bytes=pdf_bytes,
        )
        return self._agreements.add(record)

    def publish_closed_topics_for_period(
        self,
        period_id: str,
        *,
        client_id: str | None,
    ) -> list[AgreementRecord]:
        """Publish agreements for every closed topic in a period."""
        published: list[AgreementRecord] = []
        for topic in self._topics.list_topics():
            if topic.period_id != period_id or topic.status_id != CLOSED_STATUS_ID:
                continue
            item = self.publish_from_topic(topic.id, client_id=client_id)
            if item is not None:
                published.append(item)
        return published

    def _building_name(self, client_id: str | None) -> str | None:
        if not client_id or self._clients is None:
            return None
        client = self._clients.get_client(client_id)
        return client.name if client is not None else None

    def _vote_result(self, yes_count: int, no_count: int, abstain_count: int) -> str:
        if yes_count == 0 and no_count == 0 and abstain_count == 0:
            return VOTE_RESULT_NO_VOTES
        if yes_count > no_count:
            return VOTE_RESULT_APPROVED
        if no_count > yes_count:
            return VOTE_RESULT_REJECTED
        return VOTE_RESULT_TIED

    def _summary(
        self,
        topic: TopicRecord,
        yes_count: int,
        no_count: int,
        abstain_count: int,
        vote_result: str,
        opinions: list[TopicOpinionRecord],
    ) -> str:
        category = CATEGORY_LABELS.get(topic.category_key, topic.category_key or "—")
        result = RESULT_LABELS.get(vote_result, vote_result)
        lines = [
            f"Tema: {topic.title}",
            f"Categoría: {category}",
            f"Decisión: {topic.decision or '—'}",
            f"Resultado de la votación: {result} (a favor {yes_count}, en contra {no_count}, abstenciones {abstain_count}).",
            f"Descripción: {topic.description or '—'}",
            f"Comentarios registrados: {len(opinions)}.",
        ]
        return "\n".join(lines)

    def _summary_custom(
        self,
        topic: TopicRecord,
        option_lines: list[str],
        opinions: list[TopicOpinionRecord],
    ) -> str:
        category = CATEGORY_LABELS.get(topic.category_key, topic.category_key or "—")
        result = RESULT_LABELS.get(VOTE_RESULT_CUSTOM, "OPCIONES")
        tallies = ", ".join(option_lines) if option_lines else "sin conteos"
        lines = [
            f"Tema: {topic.title}",
            f"Categoría: {category}",
            f"Pregunta: {topic.decision or '—'}",
            f"Resultado de la votación: {result} ({tallies}).",
            f"Descripción: {topic.description or '—'}",
            f"Comentarios registrados: {len(opinions)}.",
        ]
        return "\n".join(lines)
