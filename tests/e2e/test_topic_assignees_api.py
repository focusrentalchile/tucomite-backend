"""Committee voters can list assignable people without users.view."""

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
    assert added.status_code in {201, 409}


def test_committee_voter_can_list_topic_assignees() -> None:
    _ensure_actor_on_committee()
    listed = client.get("/api/v1/topics/assignees")
    assert listed.status_code == 200
    body = listed.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    if body["items"]:
        person = body["items"][0]
        assert "id" in person
        assert "full_name" in person
        assert "email" in person
