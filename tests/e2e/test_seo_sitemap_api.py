"""End-to-end HTTP test for the dynamic sitemap."""

from fastapi.testclient import TestClient

from app.main import app


def test_sitemap_xml_is_public_and_well_formed() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/seo/sitemap.xml")

    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert response.text.startswith("<?xml")
    assert "https://tucomite.cl/home" in response.text
    assert "https://tucomite.cl/blog" in response.text
