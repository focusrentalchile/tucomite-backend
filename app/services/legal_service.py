"""Create, list, update, and delete building legal cases."""

from datetime import datetime, timezone
from uuid import uuid4

from app.domain.legal import (
    LegalCaseAttachmentRecord,
    LegalCaseNotFound,
    LegalCaseRecord,
)
from app.repositories.legal_repository import LegalRepository

ATTACHMENT_KINDS = frozenset({"image", "video", "file"})


class LegalService:
    """Application rules for legal cases scoped to one building."""

    def __init__(self, repository: LegalRepository) -> None:
        self._repository = repository

    def list_cases(self, client_id: str) -> list[LegalCaseRecord]:
        """Return every case for the building."""
        return self._repository.list_cases(client_id)

    def list_attachments_for_cases(self, case_ids: list[str]) -> list[LegalCaseAttachmentRecord]:
        """Return attachments for the given cases."""
        return self._repository.list_attachments_for_cases(case_ids)

    def create_case(
        self,
        *,
        client_id: str,
        created_by_user_id: str,
        title: str,
        description: str,
        attachments: list[dict[str, str]] | None = None,
    ) -> LegalCaseRecord:
        """Store a new legal case for the building."""
        case_id = str(uuid4())
        record = self._repository.create_case(
            LegalCaseRecord(
                id=case_id,
                client_id=client_id,
                title=title.strip(),
                description=description.strip(),
                created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                created_by_user_id=created_by_user_id,
            ),
        )
        self._repository.replace_attachments(case_id, self._normalize_attachments(case_id, attachments))
        return record

    def update_case(
        self,
        case_id: str,
        *,
        client_id: str,
        title: str,
        description: str,
        attachments: list[dict[str, str]] | None = None,
    ) -> LegalCaseRecord:
        """Update one case that belongs to the building."""
        current = self._repository.get_case(case_id)
        if current is None or current.client_id != client_id:
            raise LegalCaseNotFound(case_id)
        updated = self._repository.update_case(
            LegalCaseRecord(
                id=current.id,
                client_id=current.client_id,
                title=title.strip(),
                description=description.strip(),
                created_at=current.created_at,
                created_by_user_id=current.created_by_user_id,
            ),
        )
        if attachments is not None:
            self._repository.replace_attachments(
                case_id,
                self._normalize_attachments(case_id, attachments),
            )
        return updated

    def delete_case(self, case_id: str, *, client_id: str) -> None:
        """Delete one case that belongs to the building."""
        current = self._repository.get_case(case_id)
        if current is None or current.client_id != client_id:
            raise LegalCaseNotFound(case_id)
        self._repository.delete_case(case_id)

    def _normalize_attachments(
        self,
        case_id: str,
        attachments: list[dict[str, str]] | None,
    ) -> list[LegalCaseAttachmentRecord]:
        if not attachments:
            return []
        rows: list[LegalCaseAttachmentRecord] = []
        for item in attachments:
            kind = (item.get("kind") or "file").strip().lower()
            if kind not in ATTACHMENT_KINDS:
                kind = "file"
            name = (item.get("name") or "").strip()
            url = (item.get("url") or "").strip()
            if not name or not url:
                continue
            rows.append(
                LegalCaseAttachmentRecord(
                    id=str(uuid4()),
                    case_id=case_id,
                    kind=kind,
                    name=name,
                    url=url,
                ),
            )
        return rows
