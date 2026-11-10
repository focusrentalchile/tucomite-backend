"""MySQL table for public blog posts."""

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BlogPostModel(Base):
    """A blog article managed by the platform super admin."""

    __tablename__ = "blog_posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    seo_title: Mapped[str] = mapped_column(String(200), default="")
    keywords: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    # Data-URL covers exceed MySQL TEXT (~64KB); match topic/project attachment storage.
    cover_image: Mapped[str] = mapped_column(MEDIUMTEXT().with_variant(Text(), "sqlite"), default="")
    cover_alt: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(80), default="")
    author: Mapped[str] = mapped_column(String(120), default="")
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[object] = mapped_column(DateTime)
    updated_at: Mapped[object] = mapped_column(DateTime)
