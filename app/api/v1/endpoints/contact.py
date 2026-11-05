"""Public contact form and super-admin inbox endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_contact_service, require_super_admin
from app.domain.contact import PrivacyConsentRequired
from app.schemas.contact import (
    ContactMessageListResponse,
    ContactMessageResponse,
    CreateContactMessageRequest,
)
from app.services.contact_service import ContactService

router = APIRouter(prefix="/contact", tags=["contact"])


def _response(message) -> ContactMessageResponse:
    return ContactMessageResponse(
        id=message.id,
        name=message.name,
        email=message.email,
        message=message.message,
        privacy_accepted=message.privacy_accepted,
        privacy_accepted_at=message.privacy_accepted_at,
        created_at=message.created_at,
    )


@router.post("", response_model=ContactMessageResponse, status_code=201)
def create_contact_message(
    body: CreateContactMessageRequest,
    service: ContactService = Depends(get_contact_service),
) -> ContactMessageResponse:
    """Accept a public contact message with Chilean privacy consent."""
    try:
        created = service.create_message(
            name=body.name,
            email=body.email,
            message=body.message,
            privacy_accepted=body.privacy_accepted,
        )
    except PrivacyConsentRequired as error:
        raise HTTPException(
            status_code=422,
            detail="Privacy consent is required.",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _response(created)


@router.get("/messages", response_model=ContactMessageListResponse)
def list_contact_messages(
    service: ContactService = Depends(get_contact_service),
    _: object = Depends(require_super_admin),
) -> ContactMessageListResponse:
    """Return every contact message for the platform super admin."""
    return ContactMessageListResponse(items=[_response(item) for item in service.list_messages()])
