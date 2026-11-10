"""Load, update, render, and send platform email templates."""

from app.domain.email_templates import (
    ROLE_TO_TEMPLATE,
    EmailTemplateNotFound,
    EmailTemplateRecord,
)
from app.repositories.email_template_repository import EmailTemplateRepository
from app.services.email_service import (
    EmailNotConfigured,
    EmailSendError,
    SmtpDeliveryConfig,
    send_html_email,
)


class EmailTemplateService:
    """CRUD and delivery helpers for onboarding email templates."""

    def __init__(self, repository: EmailTemplateRepository) -> None:
        self._repository = repository

    def list_templates(self) -> list[EmailTemplateRecord]:
        """Return every editable template."""
        return self._repository.list_templates()

    def get(self, template_id: str) -> EmailTemplateRecord:
        """Load one template by id."""
        record = self._repository.get(template_id)
        if record is None:
            raise EmailTemplateNotFound()
        return record

    def update(self, template_id: str, *, subject: str, html_body: str) -> EmailTemplateRecord:
        """Update subject and HTML body for one template."""
        current = self.get(template_id)
        cleaned_subject = subject.strip()
        cleaned_html = html_body.strip()
        if not cleaned_subject or not cleaned_html:
            raise ValueError("Subject and HTML body are required.")
        return self._repository.save(
            EmailTemplateRecord(
                id=current.id,
                key=current.key,
                name=current.name,
                subject=cleaned_subject,
                html_body=cleaned_html,
                updated_at=current.updated_at,
            ),
        )

    def render(
        self,
        template: EmailTemplateRecord,
        *,
        name: str,
        building_name: str = "",
        invite_url: str = "",
        site_url: str = "https://tucomite.cl",
        logo_url: str = "https://tucomite.cl/logo-email.png",
        login_email: str = "",
        temporary_password: str = "",
    ) -> tuple[str, str]:
        """Replace placeholders in subject and HTML."""
        mapping = {
            "{{name}}": name.strip() or "hola",
            "{{building_name}}": building_name.strip() or "tu edificio",
            "{{invite_url}}": invite_url.strip() or site_url.strip() or "https://tucomite.cl/login",
            "{{site_url}}": site_url.strip() or "https://tucomite.cl",
            "{{logo_url}}": logo_url.strip() or "https://tucomite.cl/logo-email.png",
            "{{email}}": login_email.strip(),
            "{{password}}": temporary_password,
        }
        subject = template.subject
        body = template.html_body
        for key, value in mapping.items():
            subject = subject.replace(key, value)
            body = body.replace(key, value)
        return subject, body

    def send_by_key(
        self,
        *,
        template_key: str,
        to_email: str,
        name: str,
        building_name: str = "",
        invite_url: str = "",
        site_url: str = "https://tucomite.cl",
        logo_url: str = "https://tucomite.cl/logo-email.png",
        login_email: str = "",
        temporary_password: str = "",
        smtp: SmtpDeliveryConfig | None = None,
        raise_on_error: bool = False,
    ) -> bool:
        """Send one template by key. Returns False if the key is unknown."""
        template = self._repository.get_by_key(template_key)
        if template is None:
            raise EmailTemplateNotFound()
        subject, html_body = self.render(
            template,
            name=name,
            building_name=building_name,
            invite_url=invite_url,
            site_url=site_url,
            logo_url=logo_url,
            login_email=login_email or to_email,
            temporary_password=temporary_password,
        )
        try:
            send_html_email(
                to_email=to_email,
                subject=subject,
                html_body=html_body,
                smtp=smtp,
            )
        except (EmailNotConfigured, EmailSendError):
            if raise_on_error:
                raise
            return False
        return True

    def send_for_role(
        self,
        *,
        role_key: str,
        to_email: str,
        name: str,
        building_name: str = "",
        invite_url: str = "",
        site_url: str = "https://tucomite.cl",
        logo_url: str = "https://tucomite.cl/logo-email.png",
        login_email: str = "",
        temporary_password: str = "",
        smtp: SmtpDeliveryConfig | None = None,
        raise_on_error: bool = False,
    ) -> bool:
        """Send the matching invite template for a role. Returns False if skipped."""
        template_key = ROLE_TO_TEMPLATE.get(role_key.casefold())
        if template_key is None:
            return False
        return self.send_by_key(
            template_key=template_key,
            to_email=to_email,
            name=name,
            building_name=building_name,
            invite_url=invite_url,
            site_url=site_url,
            logo_url=logo_url,
            login_email=login_email,
            temporary_password=temporary_password,
            smtp=smtp,
            raise_on_error=raise_on_error,
        )
