"""Stored building projects."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectRecord:
    """A project with a title, description, photos, and period."""

    id: str
    period_id: str
    title: str
    description: str
    photo_names: str


class ProjectNotFound(Exception):
    """Raised when a project id does not exist."""
