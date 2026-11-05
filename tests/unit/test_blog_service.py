"""Unit tests for blog slug creation and updates."""

from app.domain.blog import BlogPostNotFound, BlogPostRecord
from app.services.blog_service import BlogService


class InMemoryBlogRepository:
    def __init__(self) -> None:
        self.posts: list[BlogPostRecord] = []

    def list_posts(self, *, published_only: bool = False) -> list[BlogPostRecord]:
        items = list(self.posts)
        if published_only:
            items = [item for item in items if item.published]
        return items

    def get_by_id(self, post_id: str) -> BlogPostRecord | None:
        return next((item for item in self.posts if item.id == post_id), None)

    def get_by_slug(self, slug: str) -> BlogPostRecord | None:
        return next((item for item in self.posts if item.slug == slug), None)

    def add(self, post: BlogPostRecord) -> BlogPostRecord:
        self.posts.append(post)
        return post

    def save(self, post: BlogPostRecord) -> BlogPostRecord:
        self.posts = [post if item.id == post.id else item for item in self.posts]
        return post

    def delete(self, post_id: str) -> None:
        self.posts = [item for item in self.posts if item.id != post_id]


def test_create_post_builds_slug_and_lists_published_only() -> None:
    service = BlogService(InMemoryBlogRepository())
    draft = service.create_post(
        title="Cómo votar en el comité",
        keywords="votación, comité",
        description="Guía corta.",
        body_html="<p>Hola</p>",
        cover_image="",
        published=True,
    )
    hidden = service.create_post(
        title="Borrador",
        keywords="",
        description="",
        body_html="<p>x</p>",
        cover_image="",
        published=False,
    )

    assert draft.slug == "como-votar-en-el-comite"
    published = service.list_posts(published_only=True)
    assert all(item.published for item in published)
    assert draft.id in {item.id for item in published}
    assert hidden.id not in {item.id for item in published}


def test_update_and_delete_post() -> None:
    service = BlogService(InMemoryBlogRepository())
    post = service.create_post(
        title="Primera nota",
        keywords="a",
        description="d",
        body_html="<p>1</p>",
        cover_image="",
        published=True,
    )
    updated = service.update_post(
        post.id,
        title="Nota actualizada",
        keywords="b",
        description="nueva",
        body_html="<p>2</p>",
        cover_image="data:image/png;base64,aaa",
        published=True,
    )
    assert updated.title == "Nota actualizada"
    assert updated.slug == "nota-actualizada"
    service.delete_post(post.id)
    try:
        service.get_post(post.id)
        raise AssertionError("expected BlogPostNotFound")
    except BlogPostNotFound:
        pass
