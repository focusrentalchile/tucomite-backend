"""HTTP schemas for blog posts."""

from pydantic import BaseModel, Field


class BlogPostPayload(BaseModel):
    """Create or update fields for one blog article."""

    title: str = Field(min_length=1, max_length=200)
    seo_title: str = Field(default="", max_length=200)
    keywords: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=500)
    body_html: str = Field(default="")
    cover_image: str = Field(default="")
    cover_alt: str = Field(default="", max_length=200)
    category: str = Field(default="", max_length=80)
    author: str = Field(default="", max_length=120)
    published: bool = True
    slug: str | None = Field(default=None, max_length=180)


class BlogPostResponse(BaseModel):
    """One blog article returned to clients."""

    id: str
    slug: str
    title: str
    seo_title: str
    keywords: str
    description: str
    body_html: str
    cover_image: str
    cover_alt: str
    category: str
    author: str
    published: bool
    created_at: str
    updated_at: str


class BlogPostListResponse(BaseModel):
    """Collection of blog articles."""

    items: list[BlogPostResponse]
