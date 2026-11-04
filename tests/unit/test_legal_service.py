"""Unit tests for building legal cases and counsel workflow."""

from app.domain.legal import (
    LEGAL_STATUS_FINISHED,
    LEGAL_STATUS_IN_PROGRESS,
    LEGAL_STATUS_WAITING,
    LegalCaseAttachmentRecord,
    LegalCaseMessageRecord,
    LegalCaseNotFound,
    LegalCaseRecord,
)
from app.services.legal_service import LegalService


class _MemoryLegalRepository:
    def __init__(self) -> None:
        self.cases: dict[str, LegalCaseRecord] = {}
        self.attachments: dict[str, list[LegalCaseAttachmentRecord]] = {}
        self.messages: dict[str, list[LegalCaseMessageRecord]] = {}

    def list_cases(self, client_id: str) -> list[LegalCaseRecord]:
        return [item for item in self.cases.values() if item.client_id == client_id]

    def get_case(self, case_id: str) -> LegalCaseRecord | None:
        return self.cases.get(case_id)

    def create_case(self, case: LegalCaseRecord) -> LegalCaseRecord:
        self.cases[case.id] = case
        return case

    def update_case(self, case: LegalCaseRecord) -> LegalCaseRecord:
        self.cases[case.id] = case
        return case

    def delete_case(self, case_id: str) -> None:
        self.cases.pop(case_id, None)
        self.attachments.pop(case_id, None)
        self.messages.pop(case_id, None)

    def list_attachments_for_cases(self, case_ids: list[str]) -> list[LegalCaseAttachmentRecord]:
        rows: list[LegalCaseAttachmentRecord] = []
        for case_id in case_ids:
            rows.extend(self.attachments.get(case_id, []))
        return rows

    def replace_attachments(
        self,
        case_id: str,
        attachments: list[LegalCaseAttachmentRecord],
    ) -> None:
        self.attachments[case_id] = attachments

    def list_messages(self, case_id: str) -> list[LegalCaseMessageRecord]:
        return list(self.messages.get(case_id, []))

    def add_message(self, message: LegalCaseMessageRecord) -> LegalCaseMessageRecord:
        self.messages.setdefault(message.case_id, []).append(message)
        return message


def test_create_opens_in_waiting_and_message_moves_to_in_progress() -> None:
    service = LegalService(_MemoryLegalRepository())
    created = service.create_case(
        client_id="c1",
        created_by_user_id="u1",
        title="Contrato",
        description="Revisión",
    )
    assert created.status == LEGAL_STATUS_WAITING

    opened = service.open_case(created.id, client_id="c1")
    assert opened.status == LEGAL_STATUS_IN_PROGRESS

    waiting = service.create_case(
        client_id="c1",
        created_by_user_id="u1",
        title="Otro",
        description="Detalle",
    )
    case, message = service.add_message(
        waiting.id,
        client_id="c1",
        author_user_id="legal-1",
        author_name="Legal",
        body="Estamos revisando.",
        from_legal=True,
    )
    assert case.status == LEGAL_STATUS_IN_PROGRESS
    assert message.body == "Estamos revisando."
    finished = service.set_status(case.id, client_id="c1", status=LEGAL_STATUS_FINISHED)
    assert finished.status == LEGAL_STATUS_FINISHED


def test_update_and_delete_require_same_building() -> None:
    service = LegalService(_MemoryLegalRepository())
    created = service.create_case(
        client_id="c1",
        created_by_user_id="u1",
        title="Caso",
        description="Detalle",
    )
    try:
        service.update_case(created.id, client_id="other", title="X", description="Y")
        raise AssertionError("expected LegalCaseNotFound")
    except LegalCaseNotFound:
        pass
    try:
        service.delete_case(created.id, client_id="other")
        raise AssertionError("expected LegalCaseNotFound")
    except LegalCaseNotFound:
        pass
