"""Resultado No notifies the assignee; Sí does not email."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.domain.topics import CONFIRMATION_NO, CONFIRMATION_YES, TopicConfirmationRecord, TopicRecord
from app.services.topic_notification_email import notify_topic_resultado_vote


def _topic() -> TopicRecord:
    return TopicRecord(
        id="topic-1",
        title="Ascensor",
        description="No sube.",
        category_key="maintenance",
        attachment_name="",
        decision="¿Reparamos?",
        status_id=3,
        priority_id=2,
        assignee_user_id="admin-1",
        created_at="2026-11-01T10:00:00",
        completion_note="Listo",
        completion_submitted_at="2026-11-01T12:00:00",
    )


def _confirmation(choice: str, reason: str | None = None) -> TopicConfirmationRecord:
    return TopicConfirmationRecord(
        id="conf-1",
        topic_id="topic-1",
        author_id="voter-1",
        author_name="Ana",
        created_at="2026-11-01T13:00:00",
        choice=choice,
        reason=reason,
    )


def test_resultado_yes_skips_assignee_email() -> None:
    db = MagicMock()
    with patch(
        "app.services.topic_notification_email._assignee_recipients",
        return_value=[("admin@tucomite.cl", "Admin")],
    ) as recipients:
        sent = notify_topic_resultado_vote(
            db,
            topic=_topic(),
            confirmation=_confirmation(CONFIRMATION_YES),
            client_id="client-1",
            actor_name="Ana",
        )
    assert sent == 0
    recipients.assert_not_called()


def test_resultado_no_emails_assignee_with_reason() -> None:
    db = MagicMock()
    mailer = MagicMock()
    mailer.send_by_key.return_value = True
    with (
        patch(
            "app.services.topic_notification_email._assignee_recipients",
            return_value=[("admin@tucomite.cl", "Admin")],
        ),
        patch(
            "app.services.topic_notification_email._smtp_and_mailer",
            return_value=(MagicMock(), "https://admin.tucomite.cl", "", mailer),
        ),
        patch(
            "app.services.topic_notification_email._building_name",
            return_value="Edificio Demo",
        ),
        patch("app.repositories.notification_repository.SqlNotificationRepository") as notices,
    ):
        notices.return_value.add = MagicMock()
        sent = notify_topic_resultado_vote(
            db,
            topic=_topic(),
            confirmation=_confirmation(CONFIRMATION_NO, "Falta pintura."),
            client_id="client-1",
            actor_name="Ana",
        )
    assert sent == 1
    mailer.send_by_key.assert_called_once()
    kwargs = mailer.send_by_key.call_args.kwargs
    assert kwargs["topic_status"] == "No"
    assert kwargs["topic_description"] == "Falta pintura."
    notices.return_value.add.assert_called_once()
