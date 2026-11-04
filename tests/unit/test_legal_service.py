"""Unit tests for building legal cases."""

from app.domain.legal import LegalCaseAttachmentRecord, LegalCaseNotFound, LegalCaseRecord
from app.services.legal_service import LegalService


class _MemoryLegalRepository:
    def __init__(self) -> None:
        self.cases: dict[str, LegalCaseRecord] = {}
        self.attachments: dict[str, list[LegalCaseAttachmentRecord]] = {}

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


def test_create_list_update_and_delete_legal_case() -> None:
    repo = _MemoryLegalRepository()
    service = LegalService(repo)

    created = service.create_case(
        client_id="c1",
        created_by_user_id="u1",
        title="Contrato",
        description="Revisión del contrato de mantención.",
        attachments=[{"kind": "file", "name": "contrato.pdf", "url": "data:application/pdf;base64,aaa"}],
    )
    assert created.client_id == "c1"
    assert created.title == "Contrato"
    assert len(service.list_cases("c1")) == 1
    assert len(service.list_attachments_for_cases([created.id])) == 1
    assert service.list_cases("c2") == []

    updated = service.update_case(
        created.id,
        client_id="c1",
        title="Contrato actualizado",
        description="Nueva descripción.",
        attachments=[],
    )
    assert updated.title == "Contrato actualizado"
    assert service.list_attachments_for_cases([created.id]) == []

    service.delete_case(created.id, client_id="c1")
    assert service.list_cases("c1") == []


def test_update_and_delete_require_same_building() -> None:
    repo = _MemoryLegalRepository()
    service = LegalService(repo)
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
