"""Notification records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationRecord:
    """One in-app notice."""

    id: str
    user_id: str
    kind: str
    title: str
    body: str
    created_at: str
    read_at: str | None
