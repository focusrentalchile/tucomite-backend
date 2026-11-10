"""Send onboarding emails using editable templates and platform SMTP."""

from sqlalchemy.orm import Session

from app.repositories.email_template_repository import SqlEmailTemplateRepository
from app.repositories.platform_settings_repository import SqlPlatformSettingsRepository
from app.services.email_service import SmtpDeliveryConfig
from app.services.email_template_service import EmailTemplateService
from app.services.platform_settings_service import PlatformSettingsService


def send_role_invite_email(
    db: Session,
    *,
    role_key: str,
    to_email: str,
    name: str,
    building_name: str = "",
) -> bool:
    """Best-effort invite email for a newly created user or client owner."""
    platform = PlatformSettingsService(SqlPlatformSettingsRepository(db)).get_settings()
    site_url = (platform.public_site_url or "https://tucomite.cl").rstrip("/")
    invite_url = f"{site_url}/login"
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
    return service.send_for_role(
        role_key=role_key,
        to_email=to_email,
        name=name,
        building_name=building_name,
        invite_url=invite_url,
        site_url=site_url,
        logo_url=logo_url,
        smtp=smtp,
    )
