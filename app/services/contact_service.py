"""Use cases for public contact form messages."""

import html
import logging
import uuid
from datetime import datetime, timezone

from app.core.config import settings
from app.domain.contact import ContactMessageRecord, PrivacyConsentRequired
from app.repositories.contact_repository import ContactRepository
from app.services.email_service import (
    EmailNotConfigured,
    EmailSendError,
    SmtpDeliveryConfig,
    send_html_email,
    smtp_config_from_env,
)
from app.services.support_service import SupportService

logger = logging.getLogger(__name__)


def _notify_recipients() -> list[str]:
    """Parse configured contact notification addresses."""
    return [
        item.strip().lower()
        for item in settings.contact_notify_emails.split(",")
        if item.strip() and "@" in item
    ]


def _build_contact_notify_html(
    *,
    name: str,
    email: str,
    subject: str,
    message: str,
) -> str:
    """Branded HTML for the internal contact alert."""
    safe_name = html.escape(name)
    safe_email = html.escape(email)
    safe_subject = html.escape(subject or "Consulta desde el sitio")
    safe_message = html.escape(message).replace("\n", "<br />")
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8" /><title>Nuevo contacto</title></head>
<body style="margin:0;padding:24px;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#001545;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;margin:0 auto;background:#fff;border:1px solid #d9e0ef;border-radius:16px;">
    <tr><td style="padding:24px;background:#001545;color:#fff;font-size:20px;font-weight:700;">Tu Comité · Contacto web</td></tr>
    <tr><td style="padding:24px;">
      <p style="margin:0 0 12px;font-size:16px;"><strong>Asunto:</strong> {safe_subject}</p>
      <p style="margin:0 0 8px;font-size:15px;"><strong>Nombre:</strong> {safe_name}</p>
      <p style="margin:0 0 16px;font-size:15px;"><strong>Correo:</strong> {safe_email}</p>
      <div style="padding:16px;border-left:4px solid #1554d1;background:#f0f4fc;border-radius:8px;font-size:15px;line-height:1.55;">{safe_message}</div>
    </td></tr>
  </table>
</body>
</html>"""


class ContactService:
    """Stores and lists public contact submissions."""

    def __init__(
        self,
        repository: ContactRepository,
        support_service: SupportService | None = None,
        smtp: SmtpDeliveryConfig | None = None,
    ) -> None:
        self._repository = repository
        self._support = support_service
        self._smtp = smtp

    def list_messages(self) -> list[ContactMessageRecord]:
        """Return every contact message for the super admin."""
        return self._repository.list_messages()

    def create_message(
        self,
        *,
        name: str,
        email: str,
        message: str,
        privacy_accepted: bool,
        subject: str = "",
    ) -> ContactMessageRecord:
        """Persist a contact message when privacy consent is given."""
        if not privacy_accepted:
            raise PrivacyConsentRequired()
        cleaned_name = name.strip()
        cleaned_email = email.strip().lower()
        cleaned_subject = subject.strip()
        cleaned_message = message.strip()
        if not cleaned_name or not cleaned_email or not cleaned_message:
            raise ValueError("Name, email, and message are required.")
        if "@" not in cleaned_email or "." not in cleaned_email.split("@", 1)[-1]:
            raise ValueError("A valid email is required.")
        stored_message = (
            f"Asunto: {cleaned_subject}\n\n{cleaned_message}"
            if cleaned_subject
            else cleaned_message
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
        record = ContactMessageRecord(
            id=str(uuid.uuid4()),
            name=cleaned_name,
            email=cleaned_email,
            message=stored_message,
            privacy_accepted=True,
            privacy_accepted_at=now,
            created_at=now,
            subject=cleaned_subject,
        )
        self._repository.add_message(record)
        if self._support is not None:
            self._support.create_web_message_ticket(
                contact_name=cleaned_name,
                contact_email=cleaned_email,
                message=stored_message,
            )
        self._notify_team(
            name=cleaned_name,
            email=cleaned_email,
            subject=cleaned_subject,
            message=cleaned_message,
        )
        return record

    def _notify_team(
        self,
        *,
        name: str,
        email: str,
        subject: str,
        message: str,
    ) -> None:
        """Email every configured contact inbox; never block the public submit."""
        recipients = _notify_recipients()
        if not recipients:
            return
        mail_subject = subject or "Nueva consulta desde tucomite.cl"
        html_body = _build_contact_notify_html(
            name=name,
            email=email,
            subject=mail_subject,
            message=message,
        )
        smtp = self._smtp or smtp_config_from_env()
        for to_email in recipients:
            try:
                send_html_email(
                    to_email=to_email,
                    subject=f"[Tu Comité] {mail_subject}",
                    html_body=html_body,
                    smtp=smtp,
                )
            except (EmailNotConfigured, EmailSendError) as error:
                logger.warning("Contact notify failed for %s: %s", to_email, error)
