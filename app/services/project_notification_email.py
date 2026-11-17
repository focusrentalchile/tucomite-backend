"""Best-effort email and bell notices when initiatives (projects) are created."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.domain.email_templates import TEMPLATE_PROJECT_CREATED
from app.domain.projects import ProjectRecord
from app.services.email_service import EmailNotConfigured, EmailSendError
from app.services.topic_notification_email import (
    _add_in_app_notices,
    _building_name,
    _recipients,
    _smtp_and_mailer,
    _voter_and_owner_user_ids,
)

logger = logging.getLogger(__name__)

ADMIN_PROJECTS_URL = "https://admin.tucomite.cl/projects"
NOTICE_KIND_PROJECT_CREATED = "project_created"


def notify_project_created(
    db: Session,
    *,
    project: ProjectRecord,
    client_id: str | None,
    actor_id: str,
    actor_name: str,
) -> int:
    """Email + bell committee and client when a new initiative is created."""
    resolved_client = client_id
    notices = _add_in_app_notices(
        db,
        user_ids=[
            user_id
            for user_id in _voter_and_owner_user_ids(db, resolved_client)
            if user_id != actor_id
        ],
        kind=NOTICE_KIND_PROJECT_CREATED,
        title="Nueva iniciativa",
        body=(
            f"{actor_name or 'Alguien del comité'} creó la iniciativa "
            f"«{project.title}»."
        ),
    )
    emails = _send_project_created_email(
        db,
        project=project,
        client_id=resolved_client,
        actor_name=actor_name,
    )
    return notices + emails


def _send_project_created_email(
    db: Session,
    *,
    project: ProjectRecord,
    client_id: str | None,
    actor_name: str,
) -> int:
    recipients = _recipients(db, client_id)
    if not recipients:
        return 0
    try:
        smtp, site_url, logo_url, mailer = _smtp_and_mailer(db)
    except Exception:  # noqa: BLE001
        logger.exception("Project notification skipped: could not load mail settings")
        return 0
    building = _building_name(db, client_id)
    description = (project.description or "").strip() or "Sin descripción."
    due = (project.due_date or "").strip()
    sent = 0
    for email, full_name in recipients:
        try:
            ok = mailer.send_by_key(
                template_key=TEMPLATE_PROJECT_CREATED,
                to_email=email,
                name=full_name,
                building_name=building,
                site_url=site_url,
                logo_url=logo_url,
                project_title=project.title,
                project_description=description,
                project_url=ADMIN_PROJECTS_URL,
                project_due_date=due,
                actor_name=actor_name,
                # Keep topic_* aliases so older template editors still resolve.
                topic_title=project.title,
                topic_description=description,
                topic_url=ADMIN_PROJECTS_URL,
                smtp=smtp,
                raise_on_error=True,
            )
        except EmailNotConfigured as error:
            logger.warning("Project notification skipped: SMTP is not configured (%s)", error)
            return sent
        except EmailSendError as error:
            logger.warning("Project notification failed for %s: %s", email, error)
            continue
        except Exception:  # noqa: BLE001 — never block creating an initiative on mail
            logger.exception("Unexpected project notification failure for %s", email)
            continue
        if ok:
            sent += 1
    return sent
