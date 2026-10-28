"""End-to-end HTTP tests for periods and projects on MySQL."""

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.auth import login_as_super_admin

client = TestClient(app)


def _ensure_actor_on_committee() -> None:
    login_as_super_admin(client)
    me = client.get("/api/v1/access/me")
    assert me.status_code == 200
    user_id = me.json()["id"]
    if me.json().get("is_committee_member"):
        return
    added = client.post("/api/v1/committee/members", json={"user_id": user_id})
    assert added.status_code == 201


def test_period_must_be_opened_before_creating_projects() -> None:
    _ensure_actor_on_committee()

    opened = client.post("/api/v1/periods", json={"name": "2026"})
    assert opened.status_code == 201
    period_id = opened.json()["id"]
    assert opened.json()["status"] == "open"

    periods = client.get("/api/v1/periods")
    assert periods.status_code == 200
    assert any(item["id"] == period_id and item["status"] == "open" for item in periods.json()["items"])

    created = client.post(
        "/api/v1/projects",
        json={
            "period_id": period_id,
            "title": "Fachada",
            "description": "Pintar la fachada.",
            "photo_names": "fachada.jpg",
        },
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert created.json()["period_id"] == period_id

    listed = client.get(f"/api/v1/projects?period_id={period_id}")
    assert listed.status_code == 200
    assert any(item["id"] == project_id for item in listed.json()["items"])

    updated = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"title": "Fachada norte", "description": "Pintar la fachada norte.", "photo_names": "norte.jpg"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Fachada norte"

    removed = client.delete(f"/api/v1/projects/{project_id}")
    assert removed.status_code == 204


def test_close_period_endpoint_closes_the_open_period() -> None:
    _ensure_actor_on_committee()
    opened = client.post("/api/v1/periods", json={"name": "close-me-2027"})
    assert opened.status_code == 201
    period_id = opened.json()["id"]
    closed = client.post(f"/api/v1/periods/{period_id}/close")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json()["id"] == period_id
    listed = client.get("/api/v1/periods")
    assert listed.status_code == 200
    assert all(item["id"] != period_id or item["status"] == "closed" for item in listed.json()["items"])
