"""Persistence for blog posts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.blog import BlogPostRecord
from app.models.blog import BlogPostModel


class BlogRepository:
    """Stores and loads blog posts."""

    def list_posts(self, *, published_only: bool = False) -> list[BlogPostRecord]:
        raise NotImplementedError

    def get_by_id(self, post_id: str) -> BlogPostRecord | None:
        raise NotImplementedError

    def get_by_slug(self, slug: str) -> BlogPostRecord | None:
        raise NotImplementedError

    def add(self, post: BlogPostRecord) -> BlogPostRecord:
        raise NotImplementedError

    def save(self, post: BlogPostRecord) -> BlogPostRecord:
        raise NotImplementedError

    def delete(self, post_id: str) -> None:
        raise NotImplementedError


class SqlBlogRepository(BlogRepository):
    """MySQL-backed blog repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_posts(self, *, published_only: bool = False) -> list[BlogPostRecord]:
        statement = select(BlogPostModel).order_by(BlogPostModel.created_at.desc())
        if published_only:
            statement = statement.where(BlogPostModel.published.is_(True))
        rows = self._session.scalars(statement).all()
        return [self._to_record(row) for row in rows]

    def get_by_id(self, post_id: str) -> BlogPostRecord | None:
        row = self._session.get(BlogPostModel, post_id)
        return self._to_record(row) if row is not None else None

    def get_by_slug(self, slug: str) -> BlogPostRecord | None:
        row = self._session.scalars(
            select(BlogPostModel).where(BlogPostModel.slug == slug),
        ).first()
        return self._to_record(row) if row is not None else None

    def add(self, post: BlogPostRecord) -> BlogPostRecord:
        self._session.add(
            BlogPostModel(
                id=post.id,
                slug=post.slug,
                title=post.title,
                seo_title=post.seo_title,
                keywords=post.keywords,
                description=post.description,
                body_html=post.body_html,
                cover_image=post.cover_image,
                cover_alt=post.cover_alt,
                category=post.category,
                author=post.author,
                published=post.published,
                created_at=datetime.fromisoformat(post.created_at),
                updated_at=datetime.fromisoformat(post.updated_at),
            ),
        )
        self._session.commit()
        return post

    def save(self, post: BlogPostRecord) -> BlogPostRecord:
        row = self._session.get(BlogPostModel, post.id)
        if row is None:
            return self.add(post)
        row.slug = post.slug
        row.title = post.title
        row.seo_title = post.seo_title
        row.keywords = post.keywords
        row.description = post.description
        row.body_html = post.body_html
        row.cover_image = post.cover_image
        row.cover_alt = post.cover_alt
        row.category = post.category
        row.author = post.author
        row.published = post.published
        row.updated_at = datetime.fromisoformat(post.updated_at)
        self._session.commit()
        return post

    def delete(self, post_id: str) -> None:
        row = self._session.get(BlogPostModel, post_id)
        if row is None:
            return
        self._session.delete(row)
        self._session.commit()

    def _to_record(self, row: BlogPostModel) -> BlogPostRecord:
        return BlogPostRecord(
            id=row.id,
            slug=row.slug,
            title=row.title,
            seo_title=getattr(row, "seo_title", None) or "",
            keywords=row.keywords or "",
            description=row.description or "",
            body_html=row.body_html or "",
            cover_image=row.cover_image or "",
            cover_alt=getattr(row, "cover_alt", None) or "",
            category=getattr(row, "category", None) or "",
            author=getattr(row, "author", None) or "",
            published=bool(row.published),
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
        )
