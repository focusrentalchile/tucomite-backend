"""Unit tests for public contact message storage."""

from app.domain.contact import ContactMessageRecord, PrivacyConsentRequired
from app.services.contact_service import ContactService


class MemoryContactRepository:
    def __init__(self) -> None:
        self.items: list[ContactMessageRecord] = []

    def list_messages(self) -> list[ContactMessageRecord]:
        return list(self.items)

    def add_message(self, message: ContactMessageRecord) -> None:
        self.items.append(message)


def test_create_message_requires_privacy_consent() -> None:
    service = ContactService(MemoryContactRepository())
    try:
        service.create_message(
            name="Ana",
            email="ana@edificio.cl",
            message="Hola",
            privacy_accepted=False,
        )
        assert False, "expected PrivacyConsentRequired"
    except PrivacyConsentRequired:
        pass


def test_create_message_stores_consent_timestamp() -> None:
    repository = MemoryContactRepository()
    service = ContactService(repository)
    created = service.create_message(
        name=" Ana ",
        email="Ana@Edificio.CL",
        message="Quiero una demo",
        privacy_accepted=True,
    )
    assert created.name == "Ana"
    assert created.email == "ana@edificio.cl"
    assert created.privacy_accepted is True
    assert created.privacy_accepted_at
    assert repository.list_messages() == [created]


def test_create_message_prefixes_subject_in_stored_body() -> None:
    repository = MemoryContactRepository()
    service = ContactService(repository)
    created = service.create_message(
        name="Ana",
        email="ana@edificio.cl",
        subject="Quiero registrar mi edificio en Tu Comité",
        message="Necesito ayuda para el alta.",
        privacy_accepted=True,
    )
    assert created.subject == "Quiero registrar mi edificio en Tu Comité"
    assert created.message.startswith("Asunto: Quiero registrar mi edificio en Tu Comité")


def test_notify_recipients_include_team_inboxes() -> None:
    from app.services.contact_service import _notify_recipients

    recipients = _notify_recipients()
    assert "ricardo@tucomite.cl" in recipients
    assert "hola@tucomite.cl" in recipients
    assert "javier@tucomite.cl" in recipients

