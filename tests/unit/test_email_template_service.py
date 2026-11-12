"""Unit tests for editable onboarding email templates."""

from app.domain.email_templates import (
    TEMPLATE_ADMINISTRATOR_INVITE,
    TEMPLATE_CARETAKER_INVITE,
    TEMPLATE_CLIENT_WELCOME,
    TEMPLATE_COMMITTEE_INVITE,
    TEMPLATE_RESIDENT_INVITE,
    EmailTemplateRecord,
)
from app.services.email_template_defaults import DEFAULT_TEMPLATES
from app.services.email_template_service import EmailTemplateService


class MemoryEmailTemplateRepository:
    def __init__(self) -> None:
        self.templates: dict[str, EmailTemplateRecord] = {}
        for key, defaults in DEFAULT_TEMPLATES.items():
            self.templates[key] = EmailTemplateRecord(
                id=f"id-{key}",
                key=key,
                name=defaults["name"],
                subject=defaults["subject"],
                html_body=defaults["html_body"],
                updated_at="2026-11-09T12:00:00+00:00",
            )

    def ensure_defaults(self) -> None:
        return None

    def list_templates(self) -> list[EmailTemplateRecord]:
        return list(self.templates.values())

    def get_by_key(self, key: str) -> EmailTemplateRecord | None:
        return self.templates.get(key)

    def get(self, template_id: str) -> EmailTemplateRecord | None:
        return next((item for item in self.templates.values() if item.id == template_id), None)

    def save(self, record: EmailTemplateRecord) -> EmailTemplateRecord:
        self.templates[record.key] = record
        return record


def test_render_replaces_placeholders() -> None:
    service = EmailTemplateService(MemoryEmailTemplateRepository())
    template = service.list_templates()
    client = next(item for item in template if item.key == TEMPLATE_CLIENT_WELCOME)
    subject, html = service.render(
        client,
        name="Ana Pérez",
        building_name="Edificio Norte",
        invite_url="https://tucomite.cl/login",
        site_url="https://tucomite.cl",
        logo_url="https://tucomite.cl/logo-email.png",
    )
    assert "Ana Pérez" in html
    assert "{{name}}" not in html
    assert "https://tucomite.cl/login" in html
    assert subject.startswith("¡Bienvenido")


def test_building_invite_defaults_include_register_button() -> None:
    for key in (
        TEMPLATE_COMMITTEE_INVITE,
        TEMPLATE_ADMINISTRATOR_INVITE,
        TEMPLATE_CARETAKER_INVITE,
        TEMPLATE_RESIDENT_INVITE,
    ):
        html = DEFAULT_TEMPLATES[key]["html_body"]
        assert "Regístrate" in html
        assert 'href="{{invite_url}}"' in html


def test_update_subject_and_html() -> None:
    repo = MemoryEmailTemplateRepository()
    service = EmailTemplateService(repo)
    current = repo.get_by_key(TEMPLATE_COMMITTEE_INVITE)
    assert current is not None
    updated = service.update(current.id, subject="Nuevo asunto", html_body="<p>Hola {{name}}</p>")
    assert updated.subject == "Nuevo asunto"
    assert updated.html_body == "<p>Hola {{name}}</p>"
