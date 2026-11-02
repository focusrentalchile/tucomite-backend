"""Persistence for published agreements."""

from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.agreements import AgreementDetailRecord, AgreementRecord
from app.models.agreements import AgreementModel


class AgreementRepository(Protocol):
    """Persistence port for agreements."""

    def get_by_topic(self, topic_id: str) -> AgreementRecord | None:
        """Return the agreement for one topic when present."""

    def get(self, agreement_id: str) -> AgreementDetailRecord | None:
        """Return one agreement including PDF bytes."""

    def list_agreements(self, *, client_id: str | None = None) -> list[AgreementRecord]:
        """Return agreements, optionally filtered by client."""

    def add(self, agreement: AgreementDetailRecord) -> AgreementRecord:
        """Insert one agreement."""


class SqlAgreementRepository:
    """SQLAlchemy adapter for the agreements table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_topic(self, topic_id: str) -> AgreementRecord | None:
        row = self._session.scalars(
            select(AgreementModel).where(AgreementModel.topic_id == topic_id),
        ).first()
        if row is None:
            return None
        return self._record(row)

    def get(self, agreement_id: str) -> AgreementDetailRecord | None:
        row = self._session.get(AgreementModel, agreement_id)
        if row is None:
            return None
        return self._detail(row)

    def list_agreements(self, *, client_id: str | None = None) -> list[AgreementRecord]:
        query = select(AgreementModel).order_by(AgreementModel.created_at.desc())
        if client_id is not None:
            query = query.where(AgreementModel.client_id == client_id)
        rows = self._session.scalars(query).all()
        return [self._record(row) for row in rows]

    def add(self, agreement: AgreementDetailRecord) -> AgreementRecord:
        created = datetime.fromisoformat(agreement.created_at.replace("Z", "+00:00"))
        closed = None
        if agreement.closed_at:
            closed = datetime.fromisoformat(agreement.closed_at.replace("Z", "+00:00")).replace(tzinfo=None)
        self._session.add(
            AgreementModel(
                id=agreement.id,
                topic_id=agreement.topic_id,
                period_id=agreement.period_id,
                client_id=agreement.client_id,
                title=agreement.title,
                decision=agreement.decision,
                description=agreement.description,
                category_key=agreement.category_key,
                summary=agreement.summary,
                vote_yes=agreement.vote_yes,
                vote_no=agreement.vote_no,
                vote_abstain=agreement.vote_abstain,
                vote_result=agreement.vote_result,
                closed_at=closed,
                created_at=created,
                pdf_name=agreement.pdf_name,
                pdf_bytes=agreement.pdf_bytes,
            ),
        )
        self._session.flush()
        stored = self._session.get(AgreementModel, agreement.id)
        if stored is None:
            return agreement
        return self._record(stored)

    def _record(self, row: AgreementModel) -> AgreementRecord:
        created = row.created_at
        if created is None:
            created_at = datetime.now(timezone.utc).isoformat()
        elif created.tzinfo is None:
            created_at = created.replace(tzinfo=timezone.utc).isoformat()
        else:
            created_at = created.isoformat()
        closed = row.closed_at.isoformat() if row.closed_at else None
        return AgreementRecord(
            id=row.id,
            topic_id=row.topic_id,
            period_id=row.period_id,
            client_id=row.client_id,
            title=row.title,
            decision=row.decision,
            description=row.description,
            category_key=row.category_key,
            summary=row.summary,
            vote_yes=row.vote_yes,
            vote_no=row.vote_no,
            vote_abstain=row.vote_abstain,
            vote_result=row.vote_result,
            closed_at=closed,
            created_at=created_at,
            pdf_name=row.pdf_name,
        )

    def _detail(self, row: AgreementModel) -> AgreementDetailRecord:
        base = self._record(row)
        return AgreementDetailRecord(
            id=base.id,
            topic_id=base.topic_id,
            period_id=base.period_id,
            client_id=base.client_id,
            title=base.title,
            decision=base.decision,
            description=base.description,
            category_key=base.category_key,
            summary=base.summary,
            vote_yes=base.vote_yes,
            vote_no=base.vote_no,
            vote_abstain=base.vote_abstain,
            vote_result=base.vote_result,
            closed_at=base.closed_at,
            created_at=base.created_at,
            pdf_name=base.pdf_name,
            pdf_bytes=bytes(row.pdf_bytes or b""),
        )
