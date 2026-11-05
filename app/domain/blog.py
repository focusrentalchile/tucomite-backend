"""Blog posts published on the public site."""

from dataclasses import dataclass


class BlogPostNotFound(Exception):
    """Raised when a blog post id or slug does not exist."""


class DuplicateBlogSlug(Exception):
    """Raised when another post already uses the slug."""


@dataclass(frozen=True)
class BlogPostRecord:
    """One blog article stored for the public site."""

    id: str
    slug: str
    title: str
    keywords: str
    description: str
    body_html: str
    cover_image: str
    published: bool
    created_at: str
    updated_at: str
