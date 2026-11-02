"""Stored building projects."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectAttachmentRecord:
    """One image, video, or file attached to a project."""

    id: str
    project_id: str
    kind: str
    name: str
    url: str


@dataclass(frozen=True)
class ProjectRecord:
    """A project with a title, description, date, photos, and period."""

    id: str
    period_id: str
    title: str
    description: str
    photo_names: str
    created_at: str
    due_date: str | None = None


class ProjectNotFound(Exception):
    """Raised when a project id does not exist."""


ATTACHMENT_KINDS = frozenset({"image", "video", "file"})
