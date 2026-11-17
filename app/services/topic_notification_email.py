"""Best-effort email notifications when topics are created or change column."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.domain.email_templates import (
    TEMPLATE_TOPIC_ASSIGN_READY,
    TEMPLATE_TOPIC_CREATED,
    TEMPLATE_TOPIC_DELETED,
    TEMPLATE_TOPIC_OPINION,
    TEMPLATE_TOPIC_RESULTADO_VOTE,
    TEMPLATE_TOPIC_STATUS_CHANGED,
)
from app.domain.topics import (
    CLOSED_STATUS_ID,
    CONFIRMATION_NO,
    DOING_STATUS_ID,
    OPEN_STATUS_ID,
    WAITING_STATUS_ID,
    TopicConfirmationRecord,
    TopicRecord,
)
from app.repositories.access_repository import SqlAccessRepository
from app.repositories.client_repository import SqlClientRepository
from app.repositories.committee_repository import SqlCommitteeRepository
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

TOPIC_STATUS_LABELS: dict[int, str] = {
    OPEN_STATUS_ID: "Abiertos",
    WAITING_STATUS_ID: "Esperando decisión",
    DOING_STATUS_ID: "En ejecución",
    CLOSED_STATUS_ID: "Cerrados",
}

ADMIN_TOPICS_URL = "https://admin.tucomite.cl/topics"
NOTICE_KIND_TOPIC_OPINION = "topic_opinion"
NOTICE_KIND_TOPIC_ASSIGN_READY = "topic_assign_ready"


def topic_status_label(status_id: int) -> str:
    """Spanish board-column label for a topic status id."""
    return TOPIC_STATUS_LABELS.get(status_id, "Sin estado")


def _smtp_and_mailer(db: Session) -> tuple[SmtpDeliveryConfig, str, str, EmailTemplateService]:
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
    return smtp, site_url, logo_url, EmailTemplateService(SqlEmailTemplateRepository(db))


def _building_name(db: Session, client_id: str | None) -> str:
    if not client_id:
        return "tu edificio"
    client = SqlClientRepository(db).get_client(client_id)
    return client.name if client is not None else "tu edificio"


def _recipients(
    db: Session,
    client_id: str | None,
    *,
    include_assignee: TopicRecord | None = None,
) -> list[tuple[str, str]]:
    """Unique (email, full_name) for committee, client owner, and optional assignee."""
    if not client_id:
        return []
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for member in SqlCommitteeRepository(db).list_voter_recipients(client_id):
        email = member.email.strip().casefold()
        if not email or email in seen:
            continue
        seen.add(email)
        out.append((member.email.strip(), member.full_name.strip() or member.email.strip()))
    client = SqlClientRepository(db).get_client(client_id)
    access = SqlAccessRepository(db)
    if client is not None:
        owner = access.get_user(client.admin_user_id)
        if owner is not None and not owner.account_closed_at:
            email = (owner.email or "").strip()
            key = email.casefold()
            if email and key not in seen:
                seen.add(key)
                out.append((email, (owner.full_name or email).strip()))
    if include_assignee is not None and include_assignee.assignee_user_id:
        assignee = access.get_user(include_assignee.assignee_user_id)
        if assignee is not None and not assignee.account_closed_at:
            email = (assignee.email or "").strip()
            key = email.casefold()
            if email and key not in seen:
                seen.add(key)
                out.append((email, (assignee.full_name or email).strip()))
    return out


def _assignee_recipients(db: Session, topic: TopicRecord) -> list[tuple[str, str]]:
    """Email the assigned responsible person (admin/mayordomo when assigned)."""
    if not topic.assignee_user_id:
        return []
    access = SqlAccessRepository(db)
    assignee = access.get_user(topic.assignee_user_id)
    if assignee is None or assignee.account_closed_at:
        return []
    email = (assignee.email or "").strip()
    if not email:
        return []
    return [(email, (assignee.full_name or email).strip())]


def _send_to_committee(
    db: Session,
    *,
    template_key: str,
    client_id: str | None,
    actor_name: str,
    topic: TopicRecord,
    previous_status_id: int | None = None,
    include_assignee: TopicRecord | None = None,
    exclude_emails: set[str] | None = None,
) -> int:
    skipped = {item.casefold() for item in (exclude_emails or set()) if item}
    recipients = [
        (email, name)
        for email, name in _recipients(db, client_id, include_assignee=include_assignee)
        if email.casefold() not in skipped
    ]
    if not recipients:
        return 0
    try:
        smtp, site_url, logo_url, mailer = _smtp_and_mailer(db)
    except Exception:  # noqa: BLE001
        logger.exception("Topic notification skipped: could not load mail settings")
        return 0
    building = _building_name(db, client_id)
    description = (topic.description or topic.decision or "").strip() or "Sin descripción."
    sent = 0
    for email, full_name in recipients:
        try:
            ok = mailer.send_by_key(
                template_key=template_key,
                to_email=email,
                name=full_name,
                building_name=building,
                site_url=site_url,
                logo_url=logo_url,
                topic_title=topic.title,
                topic_description=description,
                topic_status=topic_status_label(topic.status_id),
                previous_status=(
                    topic_status_label(previous_status_id)
                    if previous_status_id is not None
                    else ""
                ),
                topic_url=ADMIN_TOPICS_URL,
                actor_name=actor_name,
                smtp=smtp,
                raise_on_error=True,
            )
        except EmailNotConfigured as error:
            logger.warning("Topic notification skipped: SMTP is not configured (%s)", error)
            return sent
        except EmailSendError as error:
            logger.warning("Topic notification failed for %s: %s", email, error)
            continue
        except Exception:  # noqa: BLE001 — never block topic actions on mail
            logger.exception("Unexpected topic notification failure for %s", email)
            continue
        if ok:
            sent += 1
    return sent


def notify_topic_created(
    db: Session,
    *,
    topic: TopicRecord,
    client_id: str | None,
    actor_name: str,
) -> int:
    """Email the building client and committee that a topic was created."""
    return _send_to_committee(
        db,
        template_key=TEMPLATE_TOPIC_CREATED,
        client_id=client_id,
        actor_name=actor_name,
        topic=topic,
    )


def notify_topic_deleted(
    db: Session,
    *,
    topic: TopicRecord,
    client_id: str | None,
    actor_name: str,
) -> int:
    """Email the building client and committee that a topic was archived."""
    return _send_to_committee(
        db,
        template_key=TEMPLATE_TOPIC_DELETED,
        client_id=client_id,
        actor_name=actor_name,
        topic=topic,
    )


def notify_topic_status_changed(
    db: Session,
    *,
    topic: TopicRecord,
    previous_status_id: int,
    client_id: str | None,
    actor_name: str,
) -> int:
    """Email committee, client, and assigned responsible when a topic changes column."""
    if previous_status_id == topic.status_id:
        return 0
    return _send_to_committee(
        db,
        template_key=TEMPLATE_TOPIC_STATUS_CHANGED,
        client_id=client_id,
        actor_name=actor_name,
        topic=topic,
        previous_status_id=previous_status_id,
        include_assignee=topic if topic.status_id == CLOSED_STATUS_ID else None,
    )


def _voter_and_owner_user_ids(db: Session, client_id: str | None) -> list[str]:
    """Unique user ids for committee voters plus the client owner of one building."""
    if not client_id:
        return []
    ids: list[str] = []
    for user_id in SqlCommitteeRepository(db).list_voter_user_ids(client_id):
        if user_id and user_id not in ids:
            ids.append(user_id)
    client = SqlClientRepository(db).get_client(client_id)
    if client is not None and client.admin_user_id and client.admin_user_id not in ids:
        owner = SqlAccessRepository(db).get_user(client.admin_user_id)
        if owner is not None and not owner.account_closed_at:
            ids.append(client.admin_user_id)
    return ids


def _add_in_app_notices(
    db: Session,
    *,
    user_ids: list[str],
    kind: str,
    title: str,
    body: str,
) -> int:
    """Best-effort bell notices for each user id. Returns how many were stored."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.domain.notifications import NotificationRecord
    from app.repositories.notification_repository import SqlNotificationRepository

    repository = SqlNotificationRepository(db)
    stored = 0
    for user_id in user_ids:
        try:
            repository.add(
                NotificationRecord(
                    id=str(uuid4()),
                    user_id=user_id,
                    kind=kind,
                    title=title,
                    body=body,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    read_at=None,
                ),
            )
            stored += 1
        except Exception:  # noqa: BLE001 — never block topic actions on notices
            logger.exception("In-app notice %s failed for user %s", kind, user_id)
    return stored


def notify_topic_opinion(
    db: Session,
    *,
    topic: TopicRecord,
    author_id: str,
    author_name: str,
    client_id: str | None,
) -> int:
    """Bell + email for every committee voter and the client owner except the author."""
    resolved_client = client_id or topic.client_id
    recipients = [
        user_id
        for user_id in _voter_and_owner_user_ids(db, resolved_client)
        if user_id != author_id
    ]
    notices = 0
    if recipients:
        notices = _add_in_app_notices(
            db,
            user_ids=recipients,
            kind=NOTICE_KIND_TOPIC_OPINION,
            title="Nueva opinión",
            body=f"{author_name or 'Alguien del comité'} opinó en «{topic.title}».",
        )
    exclude_emails: set[str] = set()
    author = SqlAccessRepository(db).get_user(author_id)
    if author is not None:
        email = (author.email or "").strip()
        if email:
            exclude_emails.add(email)
    emails = _send_to_committee(
        db,
        template_key=TEMPLATE_TOPIC_OPINION,
        client_id=resolved_client,
        actor_name=author_name or "Alguien del comité",
        topic=topic,
        exclude_emails=exclude_emails,
    )
    return notices + emails


def notify_topic_assign_ready(
    db: Session,
    *,
    topic: TopicRecord,
    client_id: str | None,
    actor_name: str,
) -> int:
    """Bell + email committee and client when a vote majority makes assigning possible."""
    resolved_client = client_id or topic.client_id
    building = _building_name(db, resolved_client)
    _add_in_app_notices(
        db,
        user_ids=_voter_and_owner_user_ids(db, resolved_client),
        kind=NOTICE_KIND_TOPIC_ASSIGN_READY,
        title="Listo para asignar",
        body=f"«{topic.title}» ({building}) ya tiene los votos para asignar a un responsable.",
    )
    return _send_to_committee(
        db,
        template_key=TEMPLATE_TOPIC_ASSIGN_READY,
        client_id=resolved_client,
        actor_name=actor_name,
        topic=topic,
    )


def notify_topic_resultado_vote(
    db: Session,
    *,
    topic: TopicRecord,
    confirmation: TopicConfirmationRecord,
    client_id: str | None,
    actor_name: str,
) -> int:
    """Bell + email the assignee when Resultado is No (one notice per No reason)."""
    if (confirmation.choice or "").casefold() != CONFIRMATION_NO:
        return 0
    if not topic.assignee_user_id:
        return 0
    reason = (confirmation.reason or "").strip() or "Sin comentario adicional."
    building = _building_name(db, client_id)
    notice_body = (
        f"{actor_name} votó No en «{topic.title}» ({building}): {reason}"
    )
    try:
        from datetime import datetime, timezone
        from uuid import uuid4

        from app.domain.notifications import NotificationRecord
        from app.repositories.notification_repository import SqlNotificationRepository

        SqlNotificationRepository(db).add(
            NotificationRecord(
                id=str(uuid4()),
                user_id=topic.assignee_user_id,
                kind="topic_resultado_no",
                title="Resultado: no cumple",
                body=notice_body,
                created_at=datetime.now(timezone.utc).isoformat(),
                read_at=None,
            ),
        )
    except Exception:  # noqa: BLE001
        logger.exception("Resultado No in-app notice failed for topic %s", topic.id)

    recipients = _assignee_recipients(db, topic)
    if not recipients:
        return 0
    try:
        smtp, site_url, logo_url, mailer = _smtp_and_mailer(db)
    except Exception:  # noqa: BLE001
        logger.exception("Resultado No email skipped: could not load mail settings")
        return 0
    sent = 0
    for email, full_name in recipients:
        try:
            ok = mailer.send_by_key(
                template_key=TEMPLATE_TOPIC_RESULTADO_VOTE,
                to_email=email,
                name=full_name,
                building_name=building,
                site_url=site_url,
                logo_url=logo_url,
                topic_title=topic.title,
                topic_description=reason,
                topic_status="No",
                topic_url=ADMIN_TOPICS_URL,
                actor_name=actor_name,
                smtp=smtp,
                raise_on_error=True,
            )
        except EmailNotConfigured as error:
            logger.warning("Resultado No email skipped: SMTP is not configured (%s)", error)
            return sent
        except EmailSendError as error:
            logger.warning("Resultado No email failed for %s: %s", email, error)
            continue
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected Resultado No email failure for %s", email)
            continue
        if ok:
            sent += 1
    return sent
