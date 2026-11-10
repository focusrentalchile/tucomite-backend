"""Send onboarding emails using editable templates and platform SMTP."""

from dataclasses import dataclass
import logging

from sqlalchemy.orm import Session

from app.domain.email_templates import TEMPLATE_CLIENT_ACTIVATION
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


def _smtp_and_site(db: Session) -> tuple[SmtpDeliveryConfig, str, str, EmailTemplateService]:
    platform = PlatformSettingsService(SqlPlatformSettingsRepository(db)).get_settings()
    site_url = (platform.public_site_url or "https://tucomite.cl").rstrip("/")
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
    return smtp, site_url, logo_url, service


def _as_invite_result(to_email: str, sent: bool, *, missing_template: str) -> InviteEmailResult:
    if not sent:
        return InviteEmailResult(sent=False, error=missing_template)
    return InviteEmailResult(sent=True)


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
    smtp, site_url, logo_url, service = _smtp_and_site(db)
    invite_url = f"{site_url}/login"
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
    return _as_invite_result(to_email, sent, missing_template="No hay plantilla de correo para este rol.")


def send_client_activation_email(
    db: Session,
    *,
    to_email: str,
    name: str,
    building_name: str,
    activation_token: str,
) -> InviteEmailResult:
    """Welcome email for self-registration with an Activar cuenta button."""
    smtp, site_url, logo_url, service = _smtp_and_site(db)
    invite_url = f"{site_url}/activate?token={activation_token}"
    try:
        sent = service.send_by_key(
            template_key=TEMPLATE_CLIENT_ACTIVATION,
            to_email=to_email,
            name=name,
            building_name=building_name,
            invite_url=invite_url,
            site_url=site_url,
            logo_url=logo_url,
            login_email=to_email,
            smtp=smtp,
            raise_on_error=True,
        )
    except EmailNotConfigured as error:
        logger.warning("Activation email skipped: SMTP is not configured (%s)", error)
        return InviteEmailResult(sent=False, error="SMTP no está configurado en Ajustes de plataforma.")
    except EmailSendError as error:
        logger.warning("Activation email failed for %s: %s", to_email, error)
        return InviteEmailResult(
            sent=False,
            error=f"No se pudo enviar el correo ({error}). Revisá host/puerto SMTP.",
        )
    except Exception as error:  # noqa: BLE001 — never block account creation on mail
        logger.exception("Unexpected activation email failure for %s", to_email)
        return InviteEmailResult(sent=False, error=str(error) or "Error desconocido al enviar el correo.")
    return _as_invite_result(
        to_email,
        sent,
        missing_template="No hay plantilla de activación de cuenta.",
    )
