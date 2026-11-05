"""Unit tests for the branded agreement PDF builder."""

from app.domain.agreements import VOTE_RESULT_APPROVED, VOTE_RESULT_CUSTOM
from app.domain.topics import TopicOpinionRecord, TopicVoteRecord
from app.services.agreement_pdf_service import build_agreement_pdf


def test_build_agreement_pdf_contains_pdf_header() -> None:
    pdf = build_agreement_pdf(
        title="Cámaras del patio",
        decision="¿Instalamos cámaras en el patio?",
        description="Mejorar la seguridad del acceso.",
        category_key="security",
        vote_yes=3,
        vote_no=1,
        vote_abstain=0,
        vote_result=VOTE_RESULT_APPROVED,
        closed_at="2026-03-01T15:00:00",
        votes=[
            TopicVoteRecord(id="v1", topic_id="t1", author_id="u1", author_name="Ana", choice="yes"),
            TopicVoteRecord(id="v2", topic_id="t1", author_id="u2", author_name="Luis", choice="yes"),
            TopicVoteRecord(id="v3", topic_id="t1", author_id="u3", author_name="Marta", choice="yes"),
            TopicVoteRecord(id="v4", topic_id="t1", author_id="u4", author_name="Pedro", choice="no"),
        ],
        opinions=[
            TopicOpinionRecord(
                id="o1",
                topic_id="t1",
                author_id="u1",
                author_name="Ana",
                body="Me parece urgente.",
                created_at="2026-02-20T10:00:00",
            ),
        ],
        building_name="Edificio Norte",
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_build_agreement_pdf_supports_custom_option_tallies() -> None:
    pdf = build_agreement_pdf(
        title="Color del hall",
        decision="¿Qué color pintamos?",
        description="Elegir entre tres opciones.",
        category_key="maintenance",
        vote_yes=0,
        vote_no=0,
        vote_abstain=1,
        vote_result=VOTE_RESULT_CUSTOM,
        closed_at="2026-03-01T15:00:00",
        votes=[
            TopicVoteRecord(id="v1", topic_id="t1", author_id="u1", author_name="Ana", choice="opt-blue"),
            TopicVoteRecord(id="v2", topic_id="t1", author_id="u2", author_name="Luis", choice="abstain"),
        ],
        opinions=[],
        vote_option_counts=[("Azul", 1), ("Verde", 0)],
        vote_choice_labels={"opt-blue": "Azul", "opt-green": "Verde"},
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 800
