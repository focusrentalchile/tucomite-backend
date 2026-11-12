"""Persistence for platform email templates."""

from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.email_templates import EMAIL_TEMPLATE_KEYS, EmailTemplateRecord
from app.models.email_templates import EmailTemplateModel
from app.services.email_template_defaults import DEFAULT_TEMPLATES


def _iso(value: datetime | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.isoformat()


class EmailTemplateRepository(Protocol):
    """Port used by EmailTemplateService."""

    def ensure_defaults(self) -> None: ...

    def list_templates(self) -> list[EmailTemplateRecord]: ...

    def get_by_key(self, key: str) -> EmailTemplateRecord | None: ...

    def get(self, template_id: str) -> EmailTemplateRecord | None: ...

    def save(self, record: EmailTemplateRecord) -> EmailTemplateRecord: ...


class SqlEmailTemplateRepository:
    """SQLAlchemy adapter for email templates."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_defaults(self) -> None:
        existing = {
            row.key: row
            for row in self._session.scalars(select(EmailTemplateModel)).all()
        }
        for key in EMAIL_TEMPLATE_KEYS:
            defaults = DEFAULT_TEMPLATES[key]
            row = existing.get(key)
            if row is None:
                self._session.add(
                    EmailTemplateModel(
                        id=str(uuid4()),
                        key=key,
                        name=defaults["name"],
                        subject=defaults["subject"],
                        html_body=defaults["html_body"],
                    ),
                )
            else:
                row.name = defaults["name"]
                # Keep credentials placeholders available for newly created accounts.
                if key == "client_welcome" and "{{password}}" not in (row.html_body or ""):
                    row.subject = defaults["subject"]
                    row.html_body = defaults["html_body"]
                if key == "client_activation" and "Activar cuenta" not in (row.html_body or ""):
                    row.subject = defaults["subject"]
                    row.html_body = defaults["html_body"]
                if key == "platform_invite" and "Regístrate" not in (row.html_body or ""):
                    row.subject = defaults["subject"]
                    row.html_body = defaults["html_body"]
        self._session.flush()

    def list_templates(self) -> list[EmailTemplateRecord]:
        self.ensure_defaults()
        rows = self._session.scalars(
            select(EmailTemplateModel).order_by(EmailTemplateModel.name.asc()),
        ).all()
        order = {key: index for index, key in enumerate(EMAIL_TEMPLATE_KEYS)}
        records = [self._to_record(row) for row in rows]
        records.sort(key=lambda item: order.get(item.key, 99))
        return records

    def get_by_key(self, key: str) -> EmailTemplateRecord | None:
        self.ensure_defaults()
        row = self._session.scalars(
            select(EmailTemplateModel).where(EmailTemplateModel.key == key),
        ).first()
        if row is None:
            return None
        return self._to_record(row)

    def get(self, template_id: str) -> EmailTemplateRecord | None:
        row = self._session.get(EmailTemplateModel, template_id)
        if row is None:
            return None
        return self._to_record(row)

    def save(self, record: EmailTemplateRecord) -> EmailTemplateRecord:
        row = self._session.get(EmailTemplateModel, record.id)
        if row is None:
            raise ValueError("Template not found.")
        row.subject = record.subject
        row.html_body = record.html_body
        row.name = record.name
        self._session.flush()
        self._session.refresh(row)
        return self._to_record(row)

    def _to_record(self, row: EmailTemplateModel) -> EmailTemplateRecord:
        return EmailTemplateRecord(
            id=row.id,
            key=row.key,
            name=row.name,
            subject=row.subject,
            html_body=row.html_body,
            updated_at=_iso(row.updated_at),
        )
