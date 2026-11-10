"""Send onboarding emails using editable templates and platform SMTP."""

from dataclasses import dataclass
import logging

from sqlalchemy.orm import Session

from app.repositories.email_template_repository import SqlEmailTemplateRepository
from app.repositories.platform_settings_repository import SqlPlatformSettingsRepository
from app.services.email_service import (
    EmailNotConfigured,
    EmailSendError,
    SmtpDeliveryConfig,
)
from app.services.email_template_service import EmailTemplateService
from app.services.platform_settings_service import PlatformSettingsService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InviteEmailResult:
    """Outcome of a best-effort onboarding invite send."""

    sent: bool
    error: str = ""


def send_role_invite_email(
    db: Session,
    *,
    role_key: str,
    to_email: str,
    name: str,
    building_name: str = "",
    login_email: str = "",
    temporary_password: str = "",
) -> InviteEmailResult:
    """Best-effort invite email for a newly created user or client owner."""
    platform = PlatformSettingsService(SqlPlatformSettingsRepository(db)).get_settings()
    site_url = (platform.public_site_url or "https://tucomite.cl").rstrip("/")
    invite_url = f"{site_url}/login"
    logo_url = f"{site_url}/logo-email.png"
    smtp = SmtpDeliveryConfig(
        host=platform.smtp_host,
        port=platform.smtp_port,
        user=platform.smtp_user,
        password=platform.smtp_password,
        from_address=platform.smtp_from,
        use_tls=platform.smtp_use_tls,
    )
    service = EmailTemplateService(SqlEmailTemplateRepository(db))
    try:
        sent = service.send_for_role(
            role_key=role_key,
            to_email=to_email,
            name=name,
            building_name=building_name,
            invite_url=invite_url,
            site_url=site_url,
            logo_url=logo_url,
            login_email=login_email or to_email,
            temporary_password=temporary_password,
            smtp=smtp,
            raise_on_error=True,
        )
    except EmailNotConfigured as error:
        logger.warning("Onboarding email skipped: SMTP is not configured (%s)", error)
        return InviteEmailResult(sent=False, error="SMTP no está configurado en Ajustes de plataforma.")
    except EmailSendError as error:
        logger.warning("Onboarding email failed for %s: %s", to_email, error)
        return InviteEmailResult(
            sent=False,
            error=f"No se pudo enviar el correo ({error}). Revisá host/puerto SMTP.",
        )
    except Exception as error:  # noqa: BLE001 — never block account creation on mail
        logger.exception("Unexpected onboarding email failure for %s", to_email)
        return InviteEmailResult(sent=False, error=str(error) or "Error desconocido al enviar el correo.")
    if not sent:
        return InviteEmailResult(sent=False, error="No hay plantilla de correo para este rol.")
    return InviteEmailResult(sent=True)
