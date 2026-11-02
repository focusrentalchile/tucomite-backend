"""In-memory agreement repository for unit tests."""

from app.domain.agreements import AgreementDetailRecord, AgreementRecord


class InMemoryAgreementRepository:
    """Stores agreements in memory keyed by id."""

    def __init__(self) -> None:
        self._items: dict[str, AgreementDetailRecord] = {}

    def get_by_topic(self, topic_id: str) -> AgreementRecord | None:
        for item in self._items.values():
            if item.topic_id == topic_id:
                return item
        return None

    def get(self, agreement_id: str) -> AgreementDetailRecord | None:
        return self._items.get(agreement_id)

    def list_agreements(self, *, client_id: str | None = None) -> list[AgreementRecord]:
        items = list(self._items.values())
        if client_id is not None:
            items = [item for item in items if item.client_id == client_id]
        return sorted(items, key=lambda item: item.created_at, reverse=True)

    def add(self, agreement: AgreementDetailRecord) -> AgreementRecord:
        self._items[agreement.id] = agreement
        return agreement
