"""Create, list, resend, track, and accept invitations."""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.access_catalog import access_catalog
from app.core.config import settings
from app.domain.access import DuplicateEmail
from app.domain.email_templates import ROLE_TO_TEMPLATE, TEMPLATE_PLATFORM_INVITE
from app.domain.invitations import (
    KIND_BUILDING,
    KIND_PLATFORM,
    InvitationAlreadyUsed,
    InvitationEmailFailed,
    InvitationForbidden,
    InvitationNotFound,
    InvitationRecord,
)
from app.repositories.access_repository import AccessRepository, SqlAccessRepository
from app.repositories.client_repository import SqlClientRepository
from app.repositories.invitation_repository import InvitationRepository, SqlInvitationRepository
from app.repositories.email_template_repository import SqlEmailTemplateRepository
from app.repositories.platform_settings_repository import SqlPlatformSettingsRepository
from app.services.access_bootstrap import _ensure_starter_roles
from app.services.client_service import ClientService, DuplicateClientName
from app.services.email_service import EmailNotConfigured, EmailSendError, SmtpDeliveryConfig
from app.services.email_template_service import EmailTemplateService
from app.services.onboarding_email import InviteEmailResult
from app.services.platform_settings_service import PlatformSettingsService

logger = logging.getLogger(__name__)

ASSIGNABLE_INVITE_ROLES = frozenset(
    {"administrator", "committee", "caretaker", "resident", "legal"},
)

# 1x1 transparent GIF
_TRACKING_PIXEL = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00"
    b",\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def tracking_pixel_bytes() -> bytes:
    """Return a tiny GIF used as the email open tracker."""
    return _TRACKING_PIXEL


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _api_base() -> str:
    return (getattr(settings, "api_public_url", None) or "https://api.tucomite.cl").rstrip("/")


class InvitationService:
    """Invitation use cases for super admin, building owners, and public accept."""

    def __init__(
        self,
        repository: InvitationRepository,
        access: AccessRepository,
        db: Session,
    ) -> None:
        self._repository = repository
        self._access = access
        self._db = db

    def list_for_actor(self, *, is_super_admin: bool, client_id: str | None) -> list[InvitationRecord]:
        if is_super_admin:
            return self._repository.list_all()
        if not client_id:
            return []
        return self._repository.list_for_client(client_id)

    def create_platform(
        self,
        *,
        name: str,
        email: str,
        invited_by_user_id: str,
    ) -> tuple[InvitationRecord, InviteEmailResult]:
        cleaned_name = name.strip()
        cleaned_email = email.strip().lower()
        if not cleaned_name or "@" not in cleaned_email:
            raise ValueError("Name and a valid email are required.")
        if self._access.get_user_by_email(cleaned_email) is not None:
            raise DuplicateEmail()
        existing = self._repository.get_by_email(cleaned_email)
        if existing and not existing.registered_at:
            raise ValueError("An open invitation already exists for this email.")
        record = InvitationRecord(
            id=str(uuid.uuid4()),
            kind=KIND_PLATFORM,
            name=cleaned_name,
            email=cleaned_email,
            building_name="",
            role_key="client",
            client_id=None,
            invited_by_user_id=invited_by_user_id,
            token=secrets.token_urlsafe(32),
            sent_at=None,
            opened_at=None,
            registered_at=None,
            created_at=_now_iso(),
        )
        self._repository.add(record)
        result = self._send(record)
        if not result.sent:
            self._repository.delete(record.id)
            raise InvitationEmailFailed(result.error or "No se pudo enviar el correo.")
        record = replace(record, sent_at=_now_iso())
        self._repository.save(record)
        return record, result

    def create_building(
        self,
        *,
        name: str,
        email: str,
        role_key: str,
        client_id: str,
        invited_by_user_id: str,
    ) -> tuple[InvitationRecord, InviteEmailResult]:
        cleaned_name = name.strip()
        cleaned_email = email.strip().lower()
        cleaned_role = role_key.strip().lower()
        if cleaned_role not in ASSIGNABLE_INVITE_ROLES:
            raise ValueError("Role is not allowed for invitations.")
        if not cleaned_name or "@" not in cleaned_email:
            raise ValueError("Name and a valid email are required.")
        if self._access.get_user_by_email(cleaned_email) is not None:
            raise DuplicateEmail()
        client = SqlClientRepository(self._db).get(client_id)
        if client is None:
            raise ValueError("Building not found.")
        existing = self._repository.get_by_email(cleaned_email)
        if existing and not existing.registered_at:
            raise ValueError("An open invitation already exists for this email.")
        record = InvitationRecord(
            id=str(uuid.uuid4()),
            kind=KIND_BUILDING,
            name=cleaned_name,
            email=cleaned_email,
            building_name=client.name,
            role_key=cleaned_role,
            client_id=client_id,
            invited_by_user_id=invited_by_user_id,
            token=secrets.token_urlsafe(32),
            sent_at=None,
            opened_at=None,
            registered_at=None,
            created_at=_now_iso(),
        )
        self._repository.add(record)
        result = self._send(record)
        if not result.sent:
            self._repository.delete(record.id)
            raise InvitationEmailFailed(result.error or "No se pudo enviar el correo.")
        record = replace(record, sent_at=_now_iso())
        self._repository.save(record)
        return record, result

    def resend(
        self,
        invitation_id: str,
        *,
        is_super_admin: bool,
        client_id: str | None,
        actor_user_id: str,
    ) -> tuple[InvitationRecord, InviteEmailResult]:
        record = self._repository.get(invitation_id)
        if record is None:
            raise InvitationNotFound()
        self._assert_can_manage(record, is_super_admin=is_super_admin, client_id=client_id)
        if record.registered_at:
            raise InvitationAlreadyUsed()
        # Rotate token so old register links stop working after resend.
        record = replace(
            record,
            token=secrets.token_urlsafe(32),
            opened_at=None,
            invited_by_user_id=actor_user_id,
        )
        self._repository.save(record)
        result = self._send(record)
        if not result.sent:
            raise InvitationEmailFailed(result.error or "No se pudo enviar el correo.")
        record = replace(record, sent_at=_now_iso())
        self._repository.save(record)
        return record, result

    def delete(
        self,
        invitation_id: str,
        *,
        is_super_admin: bool,
        client_id: str | None,
    ) -> None:
        record = self._repository.get(invitation_id)
        if record is None:
            raise InvitationNotFound()
        self._assert_can_manage(record, is_super_admin=is_super_admin, client_id=client_id)
        self._repository.delete(invitation_id)

    def mark_opened(self, token: str) -> bool:
        record = self._repository.get_by_token(token)
        if record is None or record.registered_at or record.opened_at:
            return False
        self._repository.save(replace(record, opened_at=_now_iso()))
        return True

    def get_public(self, token: str) -> InvitationRecord:
        record = self._repository.get_by_token(token)
        if record is None:
            raise InvitationNotFound()
        return record

    def accept_platform(
        self,
        token: str,
        *,
        building_name: str,
        address: str,
        password: str,
    ) -> InvitationRecord:
        record = self._require_open_token(token, KIND_PLATFORM)
        license_starts = date.today().isoformat()
        license_ends = (date.today() + timedelta(days=30)).isoformat()
        clients = ClientService(SqlClientRepository(self._db), self._access)
        try:
            client, admin = clients.create_client(
                building_name.strip(),
                record.email,
                password,
                license_starts,
                license_ends,
                address=address.strip(),
                responsible_name=record.name,
                must_change_password=False,
                require_activation=False,
            )
        except DuplicateClientName as error:
            raise ValueError("Client name already exists.") from error
        except DuplicateEmail as error:
            raise DuplicateEmail() from error
        _ensure_starter_roles(self._access, access_catalog.permission_keys())
        updated = replace(
            record,
            building_name=client.name,
            client_id=client.id,
            registered_at=_now_iso(),
        )
        self._repository.save(updated)
        logger.info("Platform invitation accepted for %s as client %s", admin.email, client.id)
        return updated

    def accept_building(
        self,
        token: str,
        *,
        password: str,
        floor_number: str = "",
        apartment_number: str = "",
    ) -> InvitationRecord:
        from app.services.access_service import UserService

        record = self._require_open_token(token, KIND_BUILDING)
        if not record.client_id:
            raise ValueError("Invitation is missing a building.")
        role = next(
            (item for item in self._access.list_roles() if item.name.casefold() == record.role_key.casefold()),
            None,
        )
        if role is None:
            _ensure_starter_roles(self._access, access_catalog.permission_keys())
            role = next(
                (
                    item
                    for item in self._access.list_roles()
                    if item.name.casefold() == record.role_key.casefold()
                ),
                None,
            )
        if role is None:
            raise ValueError("Role not found.")
        users = UserService(self._access)
        try:
            users.create_user(
                full_name=record.name,
                email=record.email,
                password=password,
                role_id=role.id,
                client_id=record.client_id,
                floor_number=floor_number,
                apartment_number=apartment_number,
                must_change_password=False,
            )
        except DuplicateEmail:
            raise
        except ValueError:
            raise
        updated = replace(record, registered_at=_now_iso())
        self._repository.save(updated)
        return updated

    def _require_open_token(self, token: str, kind: str) -> InvitationRecord:
        record = self._repository.get_by_token(token)
        if record is None:
            raise InvitationNotFound()
        if record.kind != kind:
            raise ValueError("Invitation type does not match this form.")
        if record.registered_at:
            raise InvitationAlreadyUsed()
        return record

    def _assert_can_manage(
        self,
        record: InvitationRecord,
        *,
        is_super_admin: bool,
        client_id: str | None,
    ) -> None:
        if is_super_admin:
            return
        if record.kind != KIND_BUILDING or not client_id or record.client_id != client_id:
            raise InvitationForbidden()

    def _send(self, record: InvitationRecord) -> InviteEmailResult:
        platform = PlatformSettingsService(SqlPlatformSettingsRepository(self._db)).get_settings()
        site_url = (platform.public_site_url or settings.public_site_url or "https://tucomite.cl").rstrip(
            "/"
        )
        logo_url = f"{site_url}/logo-email.png"
        invite_url = f"{site_url}/register?token={record.token}"
        track_url = f"{_api_base()}/api/v1/invitations/track/{record.token}"
        smtp = SmtpDeliveryConfig(
            host=platform.smtp_host,
            port=platform.smtp_port,
            user=platform.smtp_user,
            password=platform.smtp_password,
            from_address=platform.smtp_from,
            use_tls=platform.smtp_use_tls,
        )
        service = EmailTemplateService(SqlEmailTemplateRepository(self._db))
        template_key = (
            TEMPLATE_PLATFORM_INVITE
            if record.kind == KIND_PLATFORM
            else ROLE_TO_TEMPLATE.get(record.role_key, "")
        )
        if not template_key:
            return InviteEmailResult(sent=False, error="No hay plantilla de correo para este rol.")
        try:
            # Isolate template DB work so a missing/broken table never aborts the invite row.
            with self._db.begin_nested():
                template = service._repository.get_by_key(template_key)  # noqa: SLF001
            if template is None:
                return InviteEmailResult(sent=False, error="No hay plantilla de correo para esta invitación.")
            subject, html_body = service.render(
                template,
                name=record.name,
                building_name=record.building_name,
                invite_url=invite_url,
                site_url=site_url,
                logo_url=logo_url,
                login_email=record.email,
            )
            if track_url not in html_body:
                html_body = html_body.replace(
                    "</body>",
                    f'<img src="{track_url}" width="1" height="1" alt="" style="display:none;width:1px;height:1px;" /></body>',
                )
            from app.services.email_service import send_html_email

            send_html_email(to_email=record.email, subject=subject, html_body=html_body, smtp=smtp)
        except EmailNotConfigured as error:
            logger.warning("Invitation email skipped: %s", error)
            return InviteEmailResult(sent=False, error="SMTP no está configurado en Ajustes de plataforma.")
        except EmailSendError as error:
            logger.warning("Invitation email failed for %s: %s", record.email, error)
            return InviteEmailResult(
                sent=False,
                error=f"No se pudo enviar el correo ({error}). Revisá host/puerto SMTP.",
            )
        except Exception as error:  # noqa: BLE001
            logger.exception("Unexpected invitation email failure for %s", record.email)
            return InviteEmailResult(sent=False, error=str(error) or "Error desconocido al enviar el correo.")
        return InviteEmailResult(sent=True)


def get_invitation_service(db: Session) -> InvitationService:
    """Factory used by FastAPI dependencies."""
    return InvitationService(
        SqlInvitationRepository(db),
        SqlAccessRepository(db),
        db,
    )
