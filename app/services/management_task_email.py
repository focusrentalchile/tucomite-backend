"""Best-effort email when a Gestión task is assigned to an administrator."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.domain.email_templates import TEMPLATE_MANAGEMENT_TASK_ASSIGNED
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

MANAGEMENT_URL = "https://admin.tucomite.cl/management"


def notify_management_task_assigned_email(
    db: Session,
    *,
    to_email: str,
    to_name: str,
    building_name: str,
    subject: str,
    body: str,
    actor_name: str,
) -> bool:
    """Email the assignee that a Gestión task awaits them."""
    if not to_email.strip():
        return False
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
    mailer = EmailTemplateService(SqlEmailTemplateRepository(db))
    try:
        return mailer.send_by_key(
            template_key=TEMPLATE_MANAGEMENT_TASK_ASSIGNED,
            to_email=to_email,
            name=to_name or to_email,
            building_name=building_name,
            site_url=site_url,
            logo_url=logo_url,
            topic_title=subject,
            topic_description=body,
            topic_url=MANAGEMENT_URL,
            actor_name=actor_name,
            smtp=smtp,
            raise_on_error=True,
        )
    except EmailNotConfigured as error:
        logger.warning("Gestión assignment email skipped: SMTP is not configured (%s)", error)
        return False
    except EmailSendError as error:
        logger.warning("Gestión assignment email failed for %s: %s", to_email, error)
        return False
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected Gestión assignment email failure for %s", to_email)
        return False
