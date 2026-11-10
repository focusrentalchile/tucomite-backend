"""Super-admin endpoints for editable email templates."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.domain.email_templates import EmailTemplateNotFound
from app.repositories.email_template_repository import SqlEmailTemplateRepository
from app.schemas.email_templates import (
    EmailTemplateListResponse,
    EmailTemplateResponse,
    UpdateEmailTemplateRequest,
)
from app.services.email_template_service import EmailTemplateService

router = APIRouter(prefix="/email-templates", tags=["email-templates"])


def get_email_template_service(db: Session = Depends(get_db)) -> EmailTemplateService:
    """Build an email template service for the request."""
    return EmailTemplateService(SqlEmailTemplateRepository(db))


def _response(record) -> EmailTemplateResponse:
    return EmailTemplateResponse(
        id=record.id,
        key=record.key,
        name=record.name,
        subject=record.subject,
        html_body=record.html_body,
        updated_at=record.updated_at,
    )


@router.get("", response_model=EmailTemplateListResponse)
def list_email_templates(
    service: EmailTemplateService = Depends(get_email_template_service),
    _: object = Depends(require_super_admin),
) -> EmailTemplateListResponse:
    """List every onboarding email template."""
    return EmailTemplateListResponse(items=[_response(item) for item in service.list_templates()])


@router.put("/{template_id}", response_model=EmailTemplateResponse)
def update_email_template(
    template_id: str,
    body: UpdateEmailTemplateRequest,
    service: EmailTemplateService = Depends(get_email_template_service),
    _: object = Depends(require_super_admin),
) -> EmailTemplateResponse:
    """Update subject and HTML for one template."""
    try:
        updated = service.update(
            template_id,
            subject=body.subject,
            html_body=body.html_body,
        )
    except EmailTemplateNotFound as error:
        raise HTTPException(status_code=404, detail="Email template not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _response(updated)
