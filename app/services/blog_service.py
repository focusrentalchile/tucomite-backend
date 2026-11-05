"""Create and publish blog articles for the public site."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.blog import BlogPostNotFound, BlogPostRecord, DuplicateBlogSlug
from app.repositories.blog_repository import BlogRepository

_SLUG_SAFE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_SAFE.sub("-", ascii_text).strip("-")
    return slug[:160] or "articulo"


class BlogService:
    """Manages blog posts for the super admin and the public site."""

    def __init__(self, repository: BlogRepository) -> None:
        self._repository = repository

    def list_posts(self, *, published_only: bool = False) -> list[BlogPostRecord]:
        """Return posts, optionally only those marked published."""
        return self._repository.list_posts(published_only=published_only)

    def get_post(self, post_id: str) -> BlogPostRecord:
        """Return one post by id."""
        post = self._repository.get_by_id(post_id)
        if post is None:
            raise BlogPostNotFound()
        return post

    def get_by_slug(self, slug: str, *, published_only: bool = False) -> BlogPostRecord:
        """Return one post by slug."""
        post = self._repository.get_by_slug(slug.strip())
        if post is None or (published_only and not post.published):
            raise BlogPostNotFound()
        return post

    def create_post(
        self,
        *,
        title: str,
        keywords: str,
        description: str,
        body_html: str,
        cover_image: str,
        published: bool,
        slug: str | None = None,
    ) -> BlogPostRecord:
        """Create a new blog article."""
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        resolved = self._unique_slug(slug or title)
        post = BlogPostRecord(
            id=str(uuid4()),
            slug=resolved,
            title=title.strip()[:200],
            keywords=keywords.strip()[:300],
            description=description.strip()[:500],
            body_html=body_html.strip(),
            cover_image=cover_image.strip(),
            published=published,
            created_at=now,
            updated_at=now,
        )
        return self._repository.add(post)

    def update_post(
        self,
        post_id: str,
        *,
        title: str,
        keywords: str,
        description: str,
        body_html: str,
        cover_image: str,
        published: bool,
        slug: str | None = None,
    ) -> BlogPostRecord:
        """Update an existing blog article."""
        current = self._repository.get_by_id(post_id)
        if current is None:
            raise BlogPostNotFound()
        desired = (slug or title).strip()
        resolved = self._unique_slug(desired, ignore_id=post_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        post = BlogPostRecord(
            id=current.id,
            slug=resolved,
            title=title.strip()[:200],
            keywords=keywords.strip()[:300],
            description=description.strip()[:500],
            body_html=body_html.strip(),
            cover_image=cover_image.strip(),
            published=published,
            created_at=current.created_at,
            updated_at=now,
        )
        return self._repository.save(post)

    def delete_post(self, post_id: str) -> None:
        """Remove one blog article."""
        if self._repository.get_by_id(post_id) is None:
            raise BlogPostNotFound()
        self._repository.delete(post_id)

    def _unique_slug(self, raw: str, *, ignore_id: str | None = None) -> str:
        base = _slugify(raw)
        candidate = base
        suffix = 2
        while True:
            existing = self._repository.get_by_slug(candidate)
            if existing is None or existing.id == ignore_id:
                return candidate
            if suffix > 50:
                raise DuplicateBlogSlug()
            candidate = f"{base}-{suffix}"
            suffix += 1
