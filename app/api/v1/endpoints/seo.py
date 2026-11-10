"""Public SEO helpers such as the dynamic sitemap."""

from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_blog_service
from app.core.config import settings
from app.services.blog_service import BlogService

router = APIRouter(prefix="/seo", tags=["seo"])

_STATIC_PAGES: tuple[tuple[str, str, str], ...] = (
    ("/home", "weekly", "1.0"),
    ("/about", "monthly", "0.8"),
    ("/product", "monthly", "0.9"),
    ("/blog", "weekly", "0.8"),
    ("/contact", "monthly", "0.7"),
    ("/faq", "monthly", "0.7"),
    ("/terms-of-service", "yearly", "0.3"),
)


def _url_entry(loc: str, changefreq: str, priority: str, lastmod: str | None = None) -> str:
    """Build one sitemap <url> node."""
    parts = ["  <url>", f"    <loc>{escape(loc)}</loc>"]
    if lastmod:
        parts.append(f"    <lastmod>{escape(lastmod)}</lastmod>")
    parts.append(f"    <changefreq>{escape(changefreq)}</changefreq>")
    parts.append(f"    <priority>{escape(priority)}</priority>")
    parts.append("  </url>")
    return "\n".join(parts)


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml(service: BlogService = Depends(get_blog_service)) -> Response:
    """Return a sitemap that includes static public pages and published articles."""
    origin = settings.public_site_url.rstrip("/")
    entries = [
        _url_entry(f"{origin}{path}", changefreq, priority) for path, changefreq, priority in _STATIC_PAGES
    ]

    for post in service.list_posts(published_only=True):
        lastmod = (post.updated_at or post.created_at or "")[:10] or None
        entries.append(_url_entry(f"{origin}/blog/{post.slug}", "weekly", "0.7", lastmod))

    body = '<?xml version="1.0" encoding="UTF-8"?>\n'
    body += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    body += "\n".join(entries)
    body += "\n</urlset>\n"
    return Response(content=body, media_type="application/xml; charset=utf-8")
