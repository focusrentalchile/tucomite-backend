"""Notify client + committee when a topic-linked Gestión task changes column."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.email_templates import (
    TEMPLATE_MANAGEMENT_TASK_COMPLETION_REVIEW,
    TEMPLATE_MANAGEMENT_TASK_STATUS_CHANGED,
)
from app.domain.management import (
    MANAGEMENT_STATUS_DONE,
    MANAGEMENT_STATUS_IN_PROGRESS,
    MANAGEMENT_STATUS_TODO,
)
from app.domain.notifications import NotificationRecord
from app.repositories.committee_repository import SqlCommitteeRepository
from app.repositories.email_template_repository import SqlEmailTemplateRepository
from app.repositories.notification_repository import SqlNotificationRepository
from app.repositories.platform_settings_repository import SqlPlatformSettingsRepository
from app.services.email_service import EmailNotConfigured, EmailSendError, SmtpDeliveryConfig
from app.services.email_template_service import EmailTemplateService
from app.services.platform_settings_service import PlatformSettingsService

logger = logging.getLogger(__name__)

TOPICS_URL = "https://admin.tucomite.cl/topics"
MANAGEMENT_URL = "https://admin.tucomite.cl/management"

STATUS_LABELS = {
    MANAGEMENT_STATUS_TODO: "Tareas",
    MANAGEMENT_STATUS_IN_PROGRESS: "En proceso",
    MANAGEMENT_STATUS_DONE: "Finalizadas",
}


def _smtp(db: Session) -> tuple[SmtpDeliveryConfig, str, str]:
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
    return smtp, site_url, logo_url


def notify_management_status_changed(
    db: Session,
    *,
    client_id: str | None,
    building_name: str,
    subject: str,
    previous_status: str,
    next_status: str,
    actor_name: str,
) -> None:
    """Bell + email to every committee voter (includes client) for topic-linked moves."""
    if not client_id:
        return
    if previous_status == next_status:
        return
    recipients = SqlCommitteeRepository(db).list_voter_recipients(client_id)
    if not recipients:
        return
    now = datetime.now(timezone.utc).isoformat()
    notices = SqlNotificationRepository(db)
    previous_label = STATUS_LABELS.get(previous_status, previous_status)
    next_label = STATUS_LABELS.get(next_status, next_status)
    body = (
        f"«{subject}» en {building_name} pasó de {previous_label} a {next_label}."
    )
    for member in recipients:
        notices.add(
            NotificationRecord(
                id=str(uuid.uuid4()),
                user_id=member.user_id,
                kind="management_task_status_changed",
                title="Cambio de estado en Gestión",
                body=body,
                created_at=now,
                read_at=None,
            ),
        )
    smtp, site_url, logo_url = _smtp(db)
    mailer = EmailTemplateService(SqlEmailTemplateRepository(db))
    for member in recipients:
        if not member.email:
            continue
        try:
            mailer.send_by_key(
                template_key=TEMPLATE_MANAGEMENT_TASK_STATUS_CHANGED,
                to_email=member.email,
                name=member.full_name or member.email,
                building_name=building_name,
                site_url=site_url,
                logo_url=logo_url,
                topic_title=subject,
                topic_description=body,
                topic_url=TOPICS_URL,
                actor_name=actor_name,
                smtp=smtp,
                raise_on_error=True,
            )
        except EmailNotConfigured as error:
            logger.warning("Gestión status email skipped: SMTP is not configured (%s)", error)
            return
        except EmailSendError as error:
            logger.warning("Gestión status email failed for %s: %s", member.email, error)
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected Gestión status email failure for %s", member.email)


def notify_management_completion_for_review(
    db: Session,
    *,
    client_id: str | None,
    building_name: str,
    subject: str,
    note: str,
    actor_name: str,
) -> None:
    """Tell voters the administrator finished work and they should review/confirm."""
    if not client_id:
        return
    recipients = SqlCommitteeRepository(db).list_voter_recipients(client_id)
    if not recipients:
        return
    now = datetime.now(timezone.utc).isoformat()
    notices = SqlNotificationRepository(db)
    body = (
        f"«{subject}» en {building_name} ya tiene resultado del administrador. "
        "Revisa la evidencia y confirma si se culmina."
    )
    for member in recipients:
        notices.add(
            NotificationRecord(
                id=str(uuid.uuid4()),
                user_id=member.user_id,
                kind="management_task_completion_review",
                title="Resultado listo para revisar",
                body=body,
                created_at=now,
                read_at=None,
            ),
        )
    smtp, site_url, logo_url = _smtp(db)
    mailer = EmailTemplateService(SqlEmailTemplateRepository(db))
    for member in recipients:
        if not member.email:
            continue
        try:
            mailer.send_by_key(
                template_key=TEMPLATE_MANAGEMENT_TASK_COMPLETION_REVIEW,
                to_email=member.email,
                name=member.full_name or member.email,
                building_name=building_name,
                site_url=site_url,
                logo_url=logo_url,
                topic_title=subject,
                topic_description=note,
                topic_url=TOPICS_URL,
                actor_name=actor_name,
                smtp=smtp,
                raise_on_error=True,
            )
        except EmailNotConfigured as error:
            logger.warning("Gestión completion email skipped: SMTP is not configured (%s)", error)
            return
        except EmailSendError as error:
            logger.warning("Gestión completion email failed for %s: %s", member.email, error)
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected Gestión completion email failure for %s", member.email)
