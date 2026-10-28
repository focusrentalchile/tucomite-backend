"""In-app notification endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import Actor, get_current_actor
from app.core.database import get_db
from app.repositories.notification_repository import SqlNotificationRepository
from app.schemas.notifications import NotificationListResponse, NotificationResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _response(record) -> NotificationResponse:
    return NotificationResponse(
        id=record.id,
        kind=record.kind,
        title=record.title,
        body=record.body,
        created_at=record.created_at,
        read_at=record.read_at,
    )


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    """Return notices for the signed-in person."""
    items = SqlNotificationRepository(db).list_for_user(actor.user_id)
    return NotificationListResponse(items=[_response(item) for item in items])


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: str,
    actor: Actor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> NotificationResponse:
    """Mark one notice as read."""
    record = SqlNotificationRepository(db).mark_read(notification_id, actor.user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return _response(record)
