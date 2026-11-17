"""Unit tests for initiative (project) create notices."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import app.services.project_notification_email as project_mail
from app.domain.email_templates import EMAIL_TEMPLATE_KEYS, TEMPLATE_PROJECT_CREATED
from app.domain.projects import ProjectRecord
from app.services.email_template_defaults import DEFAULT_TEMPLATES


def _project() -> ProjectRecord:
    return ProjectRecord(
        id="p1",
        period_id="period-1",
        title="Pintura del hall",
        description="Renovar el color del acceso.",
        photo_names="",
        created_at="2026-11-17T12:00:00",
        due_date="2026-12-01",
    )


def test_project_created_email_template_is_registered() -> None:
    assert TEMPLATE_PROJECT_CREATED == "project_created"
    assert TEMPLATE_PROJECT_CREATED in EMAIL_TEMPLATE_KEYS
    defaults = DEFAULT_TEMPLATES[TEMPLATE_PROJECT_CREATED]
    assert "iniciativa" in defaults["subject"].casefold()
    assert "{{project_title}}" in defaults["subject"]
    assert "{{project_url}}" in defaults["html_body"]
    assert "Abre Iniciativas" in defaults["html_body"]


def test_notify_project_created_sends_notice_and_email() -> None:
    added: list[dict] = []
    with (
        patch.object(
            project_mail,
            "_voter_and_owner_user_ids",
            return_value=["author", "voter-1", "owner-1"],
        ),
        patch.object(
            project_mail,
            "_add_in_app_notices",
            side_effect=lambda db, **kwargs: added.append(kwargs) or len(kwargs["user_ids"]),
        ),
        patch.object(project_mail, "_send_project_created_email", return_value=2) as send,
    ):
        total = project_mail.notify_project_created(
            MagicMock(),
            project=_project(),
            client_id="client-1",
            actor_id="author",
            actor_name="Ana",
        )

    assert total == 4
    assert added[0]["user_ids"] == ["voter-1", "owner-1"]
    assert added[0]["kind"] == "project_created"
    assert added[0]["title"] == "Nueva iniciativa"
    assert "Ana" in added[0]["body"]
    assert "Pintura del hall" in added[0]["body"]
    assert send.call_args.kwargs["project"].title == "Pintura del hall"
