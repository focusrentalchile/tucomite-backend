"""Create, list, update, and work building legal cases."""

from datetime import datetime, timezone
from uuid import uuid4

from app.domain.legal import (
    LEGAL_STATUS_FINISHED,
    LEGAL_STATUS_IN_PROGRESS,
    LEGAL_STATUS_WAITING,
    LEGAL_STATUSES,
    InvalidLegalStatus,
    LegalCaseAttachmentRecord,
    LegalCaseMessageRecord,
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

    def list_messages(self, case_id: str, *, client_id: str) -> list[LegalCaseMessageRecord]:
        """Return the message thread for one case in the building."""
        current = self._require_case(case_id, client_id)
        return self._repository.list_messages(current.id)

    def create_case(
        self,
        *,
        client_id: str,
        created_by_user_id: str,
        title: str,
        description: str,
        attachments: list[dict[str, str]] | None = None,
    ) -> LegalCaseRecord:
        """Store a new legal case in En espera."""
        case_id = str(uuid4())
        record = self._repository.create_case(
            LegalCaseRecord(
                id=case_id,
                client_id=client_id,
                title=title.strip(),
                description=description.strip(),
                created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                created_by_user_id=created_by_user_id,
                status=LEGAL_STATUS_WAITING,
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
        """Update title/description for one case that belongs to the building."""
        current = self._require_case(case_id, client_id)
        updated = self._repository.update_case(
            LegalCaseRecord(
                id=current.id,
                client_id=current.client_id,
                title=title.strip(),
                description=description.strip(),
                created_at=current.created_at,
                created_by_user_id=current.created_by_user_id,
                status=current.status,
            ),
        )
        if attachments is not None:
            self._repository.replace_attachments(
                case_id,
                self._normalize_attachments(case_id, attachments),
            )
        return updated

    def open_case(self, case_id: str, *, client_id: str) -> LegalCaseRecord:
        """Move a waiting case to En proceso when counsel opens it."""
        current = self._require_case(case_id, client_id)
        if current.status == LEGAL_STATUS_WAITING:
            return self._set_status(current, LEGAL_STATUS_IN_PROGRESS)
        return current

    def set_status(self, case_id: str, *, client_id: str, status: str) -> LegalCaseRecord:
        """Set an explicit board status for one case."""
        cleaned = status.strip().lower()
        if cleaned not in LEGAL_STATUSES:
            raise InvalidLegalStatus(cleaned)
        current = self._require_case(case_id, client_id)
        return self._set_status(current, cleaned)

    def add_message(
        self,
        case_id: str,
        *,
        client_id: str,
        author_user_id: str,
        author_name: str,
        body: str,
        from_legal: bool,
    ) -> tuple[LegalCaseRecord, LegalCaseMessageRecord]:
        """Post a message and move waiting cases to En proceso."""
        current = self._require_case(case_id, client_id)
        cleaned = body.strip()
        if not cleaned:
            raise ValueError("Message body is required.")
        message = self._repository.add_message(
            LegalCaseMessageRecord(
                id=str(uuid4()),
                case_id=current.id,
                author_user_id=author_user_id,
                author_name=author_name.strip(),
                body=cleaned,
                from_legal=from_legal,
                created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            ),
        )
        if current.status == LEGAL_STATUS_WAITING:
            current = self._set_status(current, LEGAL_STATUS_IN_PROGRESS)
        return current, message

    def delete_case(self, case_id: str, *, client_id: str) -> None:
        """Delete one case that belongs to the building."""
        current = self._require_case(case_id, client_id)
        self._repository.delete_case(current.id)

    def _require_case(self, case_id: str, client_id: str) -> LegalCaseRecord:
        current = self._repository.get_case(case_id)
        if current is None or current.client_id != client_id:
            raise LegalCaseNotFound(case_id)
        return current

    def _set_status(self, current: LegalCaseRecord, status: str) -> LegalCaseRecord:
        if current.status == status:
            return current
        if status == LEGAL_STATUS_FINISHED and current.status not in {
            LEGAL_STATUS_IN_PROGRESS,
            LEGAL_STATUS_FINISHED,
        }:
            # Allow finishing from waiting as well for counsel convenience.
            pass
        return self._repository.update_case(
            LegalCaseRecord(
                id=current.id,
                client_id=current.client_id,
                title=current.title,
                description=current.description,
                created_at=current.created_at,
                created_by_user_id=current.created_by_user_id,
                status=status,
            ),
        )

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
