"""Unit tests for topic create/status email notifications."""

from __future__ import annotations

from dataclasses import dataclass

import app.services.topic_notification_email as topic_mail
from app.domain.email_templates import (
    TEMPLATE_TOPIC_CREATED,
    TEMPLATE_TOPIC_STATUS_CHANGED,
)
from app.domain.topics import OPEN_STATUS_ID, WAITING_STATUS_ID, TopicRecord
from app.services.email_template_defaults import DEFAULT_TEMPLATES


@dataclass
class _Member:
    user_id: str
    full_name: str
    email: str


@dataclass
class _Client:
    id: str
    name: str
    admin_user_id: str


@dataclass
class _User:
    id: str
    full_name: str
    email: str
    account_closed_at: str | None = None


class _FakeCommitteeRepo:
    def __init__(self, members: list[_Member]) -> None:
        self._members = members

    def list_voter_recipients(self, client_id: str) -> list[_Member]:
        assert client_id == "client-1"
        return self._members


class _FakeClientRepo:
    def get_client(self, client_id: str) -> _Client | None:
        if client_id != "client-1":
            return None
        return _Client(id="client-1", name="Edificio Norte", admin_user_id="owner-1")


class _FakeAccessRepo:
    def get_user(self, user_id: str) -> _User | None:
        if user_id == "owner-1":
            return _User(id="owner-1", full_name="Cliente Dueño", email="cliente@demo.local")
        return None


class _FakeMailer:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def send_by_key(self, **kwargs):  # noqa: ANN003
        self.calls.append(
            {
                "template_key": kwargs["template_key"],
                "to_email": kwargs["to_email"],
                "name": kwargs["name"],
                "topic_title": kwargs["topic_title"],
                "topic_status": kwargs["topic_status"],
                "previous_status": kwargs.get("previous_status", ""),
                "actor_name": kwargs["actor_name"],
            },
        )
        return True


def _topic(*, status_id: int = OPEN_STATUS_ID) -> TopicRecord:
    return TopicRecord(
        "topic-1",
        "Filtración hall",
        "Hay humedad en el hall.",
        "maintenance",
        "",
        "¿Reparamos?",
        status_id,
        2,
        period_id="per-1",
        client_id="client-1",
        created_at="2026-11-16T12:00:00",
    )


def test_topic_templates_use_branded_shell_and_placeholders() -> None:
    created = DEFAULT_TEMPLATES[TEMPLATE_TOPIC_CREATED]
    changed = DEFAULT_TEMPLATES[TEMPLATE_TOPIC_STATUS_CHANGED]
    assert "TuComité" in created["html_body"] or "{{logo_url}}" in created["html_body"]
    assert "{{topic_title}}" in created["html_body"]
    assert "{{topic_status}}" in created["html_body"]
    assert "{{previous_status}}" in changed["html_body"]
    assert "Ver temas" in created["html_body"]
    assert "Ver temas" in changed["html_body"]


def test_notify_topic_created_emails_client_and_committee(monkeypatch) -> None:
    mailer = _FakeMailer()
    monkeypatch.setattr(
        topic_mail,
        "SqlCommitteeRepository",
        lambda db: _FakeCommitteeRepo(
            [
                _Member("u1", "Comité Uno", "comite1@demo.local"),
                _Member("u2", "Comité Dos", "comite2@demo.local"),
                _Member("owner-1", "Cliente Dueño", "cliente@demo.local"),
            ],
        ),
    )
    monkeypatch.setattr(topic_mail, "SqlClientRepository", lambda db: _FakeClientRepo())
    monkeypatch.setattr(topic_mail, "SqlAccessRepository", lambda db: _FakeAccessRepo())
    monkeypatch.setattr(
        topic_mail,
        "_smtp_and_mailer",
        lambda db: (object(), "https://tucomite.cl", "https://tucomite.cl/logo-email.png", mailer),
    )

    sent = topic_mail.notify_topic_created(
        object(),
        topic=_topic(),
        client_id="client-1",
        actor_name="Comité Uno",
    )
    assert sent == 3
    emails = sorted(call["to_email"] for call in mailer.calls)
    assert emails == ["cliente@demo.local", "comite1@demo.local", "comite2@demo.local"]
    assert all(call["template_key"] == TEMPLATE_TOPIC_CREATED for call in mailer.calls)
    assert mailer.calls[0]["topic_title"] == "Filtración hall"
    assert mailer.calls[0]["topic_status"] == "Abiertos"


def test_notify_topic_status_changed_skips_same_column(monkeypatch) -> None:
    mailer = _FakeMailer()
    monkeypatch.setattr(
        topic_mail,
        "SqlCommitteeRepository",
        lambda db: _FakeCommitteeRepo([_Member("u1", "Comité Uno", "comite1@demo.local")]),
    )
    monkeypatch.setattr(topic_mail, "SqlClientRepository", lambda db: _FakeClientRepo())
    monkeypatch.setattr(topic_mail, "SqlAccessRepository", lambda db: _FakeAccessRepo())
    monkeypatch.setattr(
        topic_mail,
        "_smtp_and_mailer",
        lambda db: (object(), "https://tucomite.cl", "https://tucomite.cl/logo-email.png", mailer),
    )

    sent = topic_mail.notify_topic_status_changed(
        object(),
        topic=_topic(status_id=WAITING_STATUS_ID),
        previous_status_id=WAITING_STATUS_ID,
        client_id="client-1",
        actor_name="Comité Uno",
    )
    assert sent == 0
    assert mailer.calls == []

    sent = topic_mail.notify_topic_status_changed(
        object(),
        topic=_topic(status_id=WAITING_STATUS_ID),
        previous_status_id=OPEN_STATUS_ID,
        client_id="client-1",
        actor_name="Comité Uno",
    )
    assert sent == 2
    assert all(call["template_key"] == TEMPLATE_TOPIC_STATUS_CHANGED for call in mailer.calls)
    assert mailer.calls[0]["previous_status"] == "Abiertos"
    assert mailer.calls[0]["topic_status"] == "Esperando decisión"
    emails = sorted(call["to_email"] for call in mailer.calls)
    assert emails == ["cliente@demo.local", "comite1@demo.local"]
