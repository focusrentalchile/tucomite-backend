"""Super-admin endpoints for platform SMTP settings."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_db, require_super_admin
from app.domain.platform_settings import PlatformSettingsRecord
from app.repositories.platform_settings_repository import SqlPlatformSettingsRepository
from app.schemas.platform_settings import PlatformSettingsResponse, UpdatePlatformSettingsRequest
from app.services.platform_settings_service import PlatformSettingsService

router = APIRouter(tags=["platform-settings"])


def _response(record: PlatformSettingsRecord) -> PlatformSettingsResponse:
    return PlatformSettingsResponse(
        smtp_host=record.smtp_host,
        smtp_port=record.smtp_port,
        smtp_user=record.smtp_user,
        smtp_from=record.smtp_from,
        smtp_use_tls=record.smtp_use_tls,
        public_site_url=record.public_site_url,
        password_set=bool(record.smtp_password.strip()),
    )


def get_platform_settings_service(db: Session = Depends(get_db)) -> PlatformSettingsService:
    """Build the platform settings service for one request."""
    return PlatformSettingsService(SqlPlatformSettingsRepository(db))


@router.get("/platform-settings", response_model=PlatformSettingsResponse)
def read_platform_settings(
    service: PlatformSettingsService = Depends(get_platform_settings_service),
    _: Actor = Depends(require_super_admin),
) -> PlatformSettingsResponse:
    """Return SMTP settings for the super admin editor."""
    return _response(service.get_settings())


@router.put("/platform-settings", response_model=PlatformSettingsResponse)
def update_platform_settings(
    body: UpdatePlatformSettingsRequest,
    service: PlatformSettingsService = Depends(get_platform_settings_service),
    _: Actor = Depends(require_super_admin),
) -> PlatformSettingsResponse:
    """Save SMTP settings edited by the super admin."""
    return _response(
        service.update_settings(
            smtp_host=body.smtp_host,
            smtp_port=body.smtp_port,
            smtp_user=body.smtp_user,
            smtp_password=body.smtp_password,
            smtp_from=body.smtp_from,
            smtp_use_tls=body.smtp_use_tls,
            public_site_url=body.public_site_url,
        ),
    )
