"""Create and publish blog articles for the public site."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.blog import BlogPostNotFound, BlogPostRecord, DuplicateBlogSlug
from app.repositories.blog_repository import BlogRepository

_SLUG_SAFE = re.compile(r"[^a-z0-9]+")
_DEFAULT_AUTHOR = "Tu Comité"


def _slugify(value: str, *, max_length: int = 160) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_SAFE.sub("-", ascii_text).strip("-")
    return slug[:max_length] or "articulo"


def suggest_slug_from_title(title: str) -> str:
    """Build a short URL slug from the first few title words (not the full title)."""
    words = [part for part in re.split(r"\s+", title.strip()) if part][:6]
    return _slugify(" ".join(words), max_length=60)


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
        seo_title: str,
        keywords: str,
        description: str,
        body_html: str,
        cover_image: str,
        cover_alt: str,
        category: str,
        author: str,
        published: bool,
        slug: str | None = None,
    ) -> BlogPostRecord:
        """Create a new blog article."""
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        cleaned_title = title.strip()[:200]
        resolved = self._unique_slug((slug or "").strip() or suggest_slug_from_title(cleaned_title))
        post = BlogPostRecord(
            id=str(uuid4()),
            slug=resolved,
            title=cleaned_title,
            seo_title=(seo_title.strip() or cleaned_title)[:200],
            keywords=keywords.strip()[:300],
            description=(description.strip() or cleaned_title)[:500],
            body_html=body_html.strip(),
            cover_image=cover_image.strip(),
            cover_alt=(cover_alt.strip() or cleaned_title)[:200],
            category=category.strip()[:80],
            author=(author.strip() or _DEFAULT_AUTHOR)[:120],
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
        seo_title: str,
        keywords: str,
        description: str,
        body_html: str,
        cover_image: str,
        cover_alt: str,
        category: str,
        author: str,
        published: bool,
        slug: str | None = None,
    ) -> BlogPostRecord:
        """Update an existing blog article."""
        current = self._repository.get_by_id(post_id)
        if current is None:
            raise BlogPostNotFound()
        cleaned_title = title.strip()[:200]
        desired = (slug or "").strip() or current.slug
        resolved = self._unique_slug(desired, ignore_id=post_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        post = BlogPostRecord(
            id=current.id,
            slug=resolved,
            title=cleaned_title,
            seo_title=(seo_title.strip() or cleaned_title)[:200],
            keywords=keywords.strip()[:300],
            description=(description.strip() or cleaned_title)[:500],
            body_html=body_html.strip(),
            cover_image=cover_image.strip(),
            cover_alt=(cover_alt.strip() or cleaned_title)[:200],
            category=category.strip()[:80],
            author=(author.strip() or _DEFAULT_AUTHOR)[:120],
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
        base = _slugify(raw, max_length=60)
        candidate = base
        suffix = 2
        while True:
            existing = self._repository.get_by_slug(candidate)
            if existing is None or existing.id == ignore_id:
                return candidate
            if suffix > 50:
                raise DuplicateBlogSlug()
            candidate = f"{base}-{suffix}"[:60]
            suffix += 1
