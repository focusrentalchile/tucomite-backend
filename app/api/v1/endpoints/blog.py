"""Public and super-admin blog endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_blog_service, require_super_admin
from app.domain.blog import BlogPostNotFound, BlogPostRecord, DuplicateBlogSlug
from app.schemas.blog import BlogPostListResponse, BlogPostPayload, BlogPostResponse
from app.services.blog_service import BlogService

router = APIRouter(prefix="/blog", tags=["blog"])


def _response(post: BlogPostRecord) -> BlogPostResponse:
    return BlogPostResponse(
        id=post.id,
        slug=post.slug,
        title=post.title,
        keywords=post.keywords,
        description=post.description,
        body_html=post.body_html,
        cover_image=post.cover_image,
        published=post.published,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


@router.get("", response_model=BlogPostListResponse)
def list_public_posts(service: BlogService = Depends(get_blog_service)) -> BlogPostListResponse:
    """Return published posts for the public site."""
    return BlogPostListResponse(items=[_response(item) for item in service.list_posts(published_only=True)])


@router.get("/manage", response_model=BlogPostListResponse)
def list_managed_posts(
    service: BlogService = Depends(get_blog_service),
    _: object = Depends(require_super_admin),
) -> BlogPostListResponse:
    """Return every post for the platform super admin."""
    return BlogPostListResponse(items=[_response(item) for item in service.list_posts()])


@router.get("/{slug}", response_model=BlogPostResponse)
def get_public_post(
    slug: str,
    service: BlogService = Depends(get_blog_service),
) -> BlogPostResponse:
    """Return one published post by slug."""
    try:
        return _response(service.get_by_slug(slug, published_only=True))
    except BlogPostNotFound as error:
        raise HTTPException(status_code=404, detail="Blog post not found.") from error


@router.post("", response_model=BlogPostResponse, status_code=201)
def create_post(
    body: BlogPostPayload,
    service: BlogService = Depends(get_blog_service),
    _: object = Depends(require_super_admin),
) -> BlogPostResponse:
    """Create a blog article."""
    try:
        post = service.create_post(
            title=body.title,
            keywords=body.keywords,
            description=body.description,
            body_html=body.body_html,
            cover_image=body.cover_image,
            published=body.published,
            slug=body.slug,
        )
    except DuplicateBlogSlug as error:
        raise HTTPException(status_code=409, detail="Slug already exists.") from error
    return _response(post)


@router.put("/{post_id}", response_model=BlogPostResponse)
def update_post(
    post_id: str,
    body: BlogPostPayload,
    service: BlogService = Depends(get_blog_service),
    _: object = Depends(require_super_admin),
) -> BlogPostResponse:
    """Update a blog article."""
    try:
        post = service.update_post(
            post_id,
            title=body.title,
            keywords=body.keywords,
            description=body.description,
            body_html=body.body_html,
            cover_image=body.cover_image,
            published=body.published,
            slug=body.slug,
        )
    except BlogPostNotFound as error:
        raise HTTPException(status_code=404, detail="Blog post not found.") from error
    except DuplicateBlogSlug as error:
        raise HTTPException(status_code=409, detail="Slug already exists.") from error
    return _response(post)


@router.delete("/{post_id}", status_code=204)
def delete_post(
    post_id: str,
    service: BlogService = Depends(get_blog_service),
    _: object = Depends(require_super_admin),
) -> None:
    """Delete a blog article."""
    try:
        service.delete_post(post_id)
    except BlogPostNotFound as error:
        raise HTTPException(status_code=404, detail="Blog post not found.") from error
