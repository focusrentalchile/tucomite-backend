"""HTTP schemas for in-app notifications."""

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    """One in-app notice."""

    id: str
    kind: str
    title: str
    body: str
    created_at: str
    read_at: str | None = None


class NotificationListResponse(BaseModel):
    """Notification collection."""

    items: list[NotificationResponse]
