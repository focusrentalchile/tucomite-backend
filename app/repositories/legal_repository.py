"""Persistence for building legal cases."""

from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.legal import (
    LEGAL_STATUS_WAITING,
    LegalCaseAttachmentRecord,
    LegalCaseMessageRecord,
    LegalCaseRecord,
)
from app.models.legal import LegalCaseAttachmentModel, LegalCaseMessageModel, LegalCaseModel


class LegalRepository(Protocol):
    """Persistence port used by the legal service."""

    def list_cases(self, client_id: str) -> list[LegalCaseRecord]:
        """Return cases for one building, newest first."""

    def get_case(self, case_id: str) -> LegalCaseRecord | None:
        """Return one case when present."""

    def create_case(self, case: LegalCaseRecord) -> LegalCaseRecord:
        """Insert one case."""

    def update_case(self, case: LegalCaseRecord) -> LegalCaseRecord:
        """Replace title, description, and status on one case."""

    def delete_case(self, case_id: str) -> None:
        """Delete one case and its attachments and messages."""

    def list_attachments_for_cases(self, case_ids: list[str]) -> list[LegalCaseAttachmentRecord]:
        """Return every attachment for the given cases."""

    def replace_attachments(
        self,
        case_id: str,
        attachments: list[LegalCaseAttachmentRecord],
    ) -> None:
        """Replace every attachment for one case."""

    def list_messages(self, case_id: str) -> list[LegalCaseMessageRecord]:
        """Return messages for one case, oldest first."""

    def add_message(self, message: LegalCaseMessageRecord) -> LegalCaseMessageRecord:
        """Insert one message on a case."""


class SqlLegalRepository:
    """SQLAlchemy adapter for legal case tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_cases(self, client_id: str) -> list[LegalCaseRecord]:
        rows = self._session.execute(
            select(LegalCaseModel)
            .where(LegalCaseModel.client_id == client_id)
            .order_by(LegalCaseModel.created_at.desc()),
        ).scalars().all()
        return [self._case(row) for row in rows]

    def get_case(self, case_id: str) -> LegalCaseRecord | None:
        row = self._session.get(LegalCaseModel, case_id)
        if row is None:
            return None
        return self._case(row)

    def create_case(self, case: LegalCaseRecord) -> LegalCaseRecord:
        created = datetime.fromisoformat(case.created_at.replace("Z", "+00:00"))
        self._session.add(
            LegalCaseModel(
                id=case.id,
                client_id=case.client_id,
                title=case.title,
                description=case.description,
                status=case.status or LEGAL_STATUS_WAITING,
                created_by_user_id=case.created_by_user_id,
                created_at=created,
            ),
        )
        self._session.flush()
        return case

    def update_case(self, case: LegalCaseRecord) -> LegalCaseRecord:
        row = self._session.get(LegalCaseModel, case.id)
        if row is None:
            raise LookupError(case.id)
        row.title = case.title
        row.description = case.description
        row.status = case.status
        self._session.flush()
        return self._case(row)

    def delete_case(self, case_id: str) -> None:
        self._session.execute(
            delete(LegalCaseMessageModel).where(LegalCaseMessageModel.case_id == case_id),
        )
        self._session.execute(
            delete(LegalCaseAttachmentModel).where(LegalCaseAttachmentModel.case_id == case_id),
        )
        row = self._session.get(LegalCaseModel, case_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    def list_attachments_for_cases(self, case_ids: list[str]) -> list[LegalCaseAttachmentRecord]:
        if not case_ids:
            return []
        rows = self._session.execute(
            select(LegalCaseAttachmentModel).where(LegalCaseAttachmentModel.case_id.in_(case_ids)),
        ).scalars().all()
        return [
            LegalCaseAttachmentRecord(
                id=row.id,
                case_id=row.case_id,
                kind=row.kind,
                name=row.name,
                url=row.url,
            )
            for row in rows
        ]

    def replace_attachments(
        self,
        case_id: str,
        attachments: list[LegalCaseAttachmentRecord],
    ) -> None:
        self._session.execute(
            delete(LegalCaseAttachmentModel).where(LegalCaseAttachmentModel.case_id == case_id),
        )
        for item in attachments:
            self._session.add(
                LegalCaseAttachmentModel(
                    id=item.id or str(uuid4()),
                    case_id=case_id,
                    kind=item.kind,
                    name=item.name,
                    url=item.url,
                ),
            )
        self._session.flush()

    def list_messages(self, case_id: str) -> list[LegalCaseMessageRecord]:
        rows = self._session.execute(
            select(LegalCaseMessageModel)
            .where(LegalCaseMessageModel.case_id == case_id)
            .order_by(LegalCaseMessageModel.created_at.asc()),
        ).scalars().all()
        return [self._message(row) for row in rows]

    def add_message(self, message: LegalCaseMessageRecord) -> LegalCaseMessageRecord:
        created = datetime.fromisoformat(message.created_at.replace("Z", "+00:00"))
        self._session.add(
            LegalCaseMessageModel(
                id=message.id,
                case_id=message.case_id,
                author_user_id=message.author_user_id,
                author_name=message.author_name,
                body=message.body,
                from_legal=message.from_legal,
                created_at=created,
            ),
        )
        self._session.flush()
        return message

    def _case(self, row: LegalCaseModel) -> LegalCaseRecord:
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return LegalCaseRecord(
            id=row.id,
            client_id=row.client_id,
            title=row.title,
            description=row.description,
            created_at=created.isoformat().replace("+00:00", "Z"),
            created_by_user_id=row.created_by_user_id,
            status=getattr(row, "status", None) or LEGAL_STATUS_WAITING,
        )

    def _message(self, row: LegalCaseMessageModel) -> LegalCaseMessageRecord:
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return LegalCaseMessageRecord(
            id=row.id,
            case_id=row.case_id,
            author_user_id=row.author_user_id,
            author_name=row.author_name,
            body=row.body,
            from_legal=bool(row.from_legal),
            created_at=created.isoformat().replace("+00:00", "Z"),
        )
