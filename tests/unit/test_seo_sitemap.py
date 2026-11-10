"""Unit tests for the public SEO sitemap endpoint."""

from fastapi import Response

from app.api.v1.endpoints.seo import sitemap_xml
from app.domain.blog import BlogPostRecord


class _FakeBlogService:
    def list_posts(self, published_only: bool = False) -> list[BlogPostRecord]:
        assert published_only is True
        return [
            BlogPostRecord(
                id="1",
                slug="convivencia",
                title="Mejor convivencia",
                keywords="comunidad",
                description="Nota",
                body_html="<p>Hola</p>",
                cover_image="",
                published=True,
                created_at="2026-03-01T10:00:00",
                updated_at="2026-03-02T11:00:00",
            )
        ]


def test_sitemap_includes_static_pages_and_published_posts() -> None:
    response = sitemap_xml(service=_FakeBlogService())  # type: ignore[arg-type]

    assert isinstance(response, Response)
    assert response.media_type == "application/xml; charset=utf-8"
    body = response.body.decode("utf-8")
    assert "https://tucomite.cl/home" in body
    assert "https://tucomite.cl/blog" in body
    assert "https://tucomite.cl/blog/convivencia" in body
    assert "<lastmod>2026-03-02</lastmod>" in body
