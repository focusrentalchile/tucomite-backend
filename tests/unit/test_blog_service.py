"""Unit tests for blog slug creation and updates."""

from app.domain.blog import BlogPostNotFound, BlogPostRecord
from app.services.blog_service import BlogService, suggest_slug_from_title


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


def test_suggest_slug_uses_short_title_fragment() -> None:
    long_title = "Cómo mejorar la convivencia en el edificio con vecinos y acuerdos claros del comité"
    assert suggest_slug_from_title(long_title) == "como-mejorar-la-convivencia-en-el"
    assert len(suggest_slug_from_title(long_title)) <= 60


def test_create_post_builds_short_slug_and_defaults_seo_fields() -> None:
    service = BlogService(InMemoryBlogRepository())
    draft = service.create_post(
        title="Cómo votar en el comité de administración del edificio",
        seo_title="",
        keywords="votación, comité",
        description="",
        body_html="<p>Hola</p>",
        cover_image="",
        cover_alt="",
        category="Consejos",
        author="",
        published=True,
    )
    hidden = service.create_post(
        title="Borrador",
        seo_title="",
        keywords="",
        description="",
        body_html="<p>x</p>",
        cover_image="",
        cover_alt="",
        category="",
        author="",
        published=False,
        slug="mi-borrador",
    )

    assert draft.slug == "como-votar-en-el-comite-de"
    assert draft.seo_title == draft.title
    assert draft.description == draft.title
    assert draft.author == "Tu Comité"
    assert draft.category == "Consejos"
    assert hidden.slug == "mi-borrador"
    published = service.list_posts(published_only=True)
    assert all(item.published for item in published)
    assert draft.id in {item.id for item in published}
    assert hidden.id not in {item.id for item in published}


def test_update_keeps_slug_unless_provided() -> None:
    service = BlogService(InMemoryBlogRepository())
    post = service.create_post(
        title="Primera nota",
        seo_title="SEO Primera",
        keywords="a",
        description="meta",
        body_html="<p>1</p>",
        cover_image="",
        cover_alt="alt",
        category="Novedades",
        author="Redacción",
        published=True,
        slug="primera",
    )
    updated = service.update_post(
        post.id,
        title="Nota actualizada con un título muy largo para no regenerar slug",
        seo_title="SEO Nueva",
        keywords="b",
        description="nueva meta",
        body_html="<p>2</p>",
        cover_image="data:image/png;base64,aaa",
        cover_alt="nueva alt",
        category="Consejos",
        author="Equipo",
        published=True,
    )
    assert updated.title.startswith("Nota actualizada")
    assert updated.slug == "primera"
    assert updated.seo_title == "SEO Nueva"
    service.delete_post(post.id)
    try:
        service.get_post(post.id)
        raise AssertionError("expected BlogPostNotFound")
    except BlogPostNotFound:
        pass
