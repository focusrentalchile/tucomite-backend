"""Unit tests for onboarding invite email rendering and SMTP failures."""

from app.domain.email_templates import EmailTemplateRecord, TEMPLATE_CLIENT_WELCOME
from app.services.email_service import EmailSendError, SmtpDeliveryConfig
from app.services.email_template_defaults import DEFAULT_TEMPLATES
from app.services.email_template_service import EmailTemplateService


class _MemoryTemplates:
    def __init__(self) -> None:
        defaults = DEFAULT_TEMPLATES[TEMPLATE_CLIENT_WELCOME]
        self.record = EmailTemplateRecord(
            id="tpl-1",
            key=TEMPLATE_CLIENT_WELCOME,
            name=defaults["name"],
            subject=defaults["subject"],
            html_body=defaults["html_body"],
            updated_at="2026-01-01T00:00:00+00:00",
        )

    def list_templates(self):
        return [self.record]

    def get(self, template_id: str):
        return self.record if template_id == self.record.id else None

    def get_by_key(self, key: str):
        return self.record if key == self.record.key else None

    def save(self, record):
        self.record = record
        return record

    def ensure_defaults(self) -> None:
        return None


def test_client_welcome_render_includes_login_credentials() -> None:
    repository = _MemoryTemplates()
    service = EmailTemplateService(repository)
    subject, body = service.render(
        repository.get_by_key(TEMPLATE_CLIENT_WELCOME),  # type: ignore[arg-type]
        name="Ana",
        building_name="Edificio Norte",
        invite_url="https://tucomite.cl/login",
        login_email="ana@edificio.cl",
        temporary_password="secreto-123",
    )
    assert "Bienvenido" in subject
    assert "ana@edificio.cl" in body
    assert "secreto-123" in body


def test_send_for_role_surfaces_smtp_errors_when_requested(monkeypatch) -> None:
    service = EmailTemplateService(_MemoryTemplates())

    def _boom(**_kwargs):
        raise EmailSendError("timed out")

    monkeypatch.setattr("app.services.email_template_service.send_html_email", _boom)
    try:
        service.send_for_role(
            role_key="client",
            to_email="ana@edificio.cl",
            name="Ana",
            smtp=SmtpDeliveryConfig(
                host="smtp.example.com",
                port=587,
                user="u",
                password="p",
                from_address="noreply@tucomite.cl",
                use_tls=True,
            ),
            raise_on_error=True,
        )
        raised = False
    except EmailSendError:
        raised = True
    assert raised
