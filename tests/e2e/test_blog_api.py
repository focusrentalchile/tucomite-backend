"""End-to-end HTTP tests for public and managed blog posts."""

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.auth import login_as_super_admin

client = TestClient(app)


def test_super_admin_can_publish_a_post_visible_on_the_public_list() -> None:
    login_as_super_admin(client)
    created = client.post(
        "/api/v1/blog",
        json={
            "title": "Guía de votaciones",
            "keywords": "votos, comité",
            "description": "Cómo votar mejor.",
            "body_html": "<p>Paso a paso</p>",
            "cover_image": "",
            "published": True,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["slug"] == "guia-de-votaciones"
    assert body["published"] is True

    public = client.get("/api/v1/blog")
    assert public.status_code == 200
    assert any(item["id"] == body["id"] for item in public.json()["items"])

    detail = client.get(f"/api/v1/blog/{body['slug']}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Guía de votaciones"

    deleted = client.delete(f"/api/v1/blog/{body['id']}")
    assert deleted.status_code == 204
