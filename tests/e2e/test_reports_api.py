"""End-to-end HTTP tests for the owner report summary."""

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.auth import login_as_super_admin

client = TestClient(app)


def test_report_summary_returns_counts() -> None:
    login_as_super_admin(client)
    response = client.get("/api/v1/reports/summary")
    assert response.status_code == 200
    body = response.json()
    assert "topics_opened" in body
    assert "topics_with_result" in body
    assert "votes_cast" in body
    assert "projects_count" in body
    assert isinstance(body["topics_opened"], int)
    assert isinstance(body["votes_cast"], int)
