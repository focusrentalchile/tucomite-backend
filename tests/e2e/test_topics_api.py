"""End-to-end HTTP tests for topics and votes on MySQL."""

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.auth import login_as_super_admin

client = TestClient(app)


def _ensure_actor_on_committee() -> str:
    login_as_super_admin(client)
    me = client.get("/api/v1/access/me")
    assert me.status_code == 200
    user_id = me.json()["id"]
    if me.json().get("is_committee_member"):
        return user_id
    added = client.post("/api/v1/committee/members", json={"user_id": user_id})
    assert added.status_code in {201, 409}
    return user_id


def test_non_member_cannot_create_a_topic() -> None:
    login_as_super_admin(client)
    me = client.get("/api/v1/access/me")
    assert me.status_code == 200
    user_id = me.json()["id"]
    if me.json().get("is_committee_member"):
        removed = client.delete(f"/api/v1/committee/members/{user_id}")
        assert removed.status_code == 204

    created = client.post(
        "/api/v1/topics",
        json={
            "title": "Solo ver",
            "description": "Sin comité.",
            "category_key": "security",
            "attachment_name": "",
            "decision": "¿Se puede?",
            "priority_id": 2,
        },
    )
    assert created.status_code == 403


def test_vote_is_stored_and_moves_topic_to_waiting() -> None:
    _ensure_actor_on_committee()
    created = client.post(
        "/api/v1/topics",
        json={
            "title": "Luminarias",
            "description": "Están apagadas.",
            "category_key": "security",
            "attachment_name": "",
            "decision": "¿Pedimos cotizaciones?",
            "priority_id": 2,
        },
    )
    assert created.status_code == 201
    topic_id = created.json()["id"]
    assert created.json()["status_id"] == 1
    assert created.json()["priority_id"] == 2
    assert created.json()["votes"] == []

    voted = client.post(f"/api/v1/topics/{topic_id}/votes", json={"choice": "yes"})
    assert voted.status_code == 200
    body = voted.json()
    assert body["topic_id"] == topic_id
    assert body["status_id"] == 2
    assert body["vote"]["choice"] == "yes"
    assert body["vote"]["author_id"]
    assert body["vote"]["author_name"]

    listed = client.get("/api/v1/topics")
    assert listed.status_code == 200
    stored = next(item for item in listed.json()["items"] if item["id"] == topic_id)
    assert stored["status_id"] == 2
    assert len(stored["votes"]) == 1
    assert stored["votes"][0]["choice"] == "yes"

    changed = client.post(f"/api/v1/topics/{topic_id}/votes", json={"choice": "no"})
    assert changed.status_code == 409
    listed_again = client.get("/api/v1/topics")
    stored_again = next(item for item in listed_again.json()["items"] if item["id"] == topic_id)
    assert len(stored_again["votes"]) == 1
    assert stored_again["votes"][0]["choice"] == "yes"


def test_topic_update_move_and_delete_survive_reload() -> None:
    _ensure_actor_on_committee()
    created = client.post(
        "/api/v1/topics",
        json={
            "title": "Portón",
            "description": "No cierra bien.",
            "category_key": "security",
            "attachment_name": "",
            "decision": "¿Lo reparamos?",
            "priority_id": 1,
        },
    )
    assert created.status_code == 201
    topic_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/topics/{topic_id}",
        json={
            "title": "Portón principal",
            "description": "No cierra bien.",
            "category_key": "maintenance",
            "attachment_name": "",
            "decision": "¿Lo reparamos?",
            "priority_id": 3,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Portón principal"

    moved = client.patch(f"/api/v1/topics/{topic_id}/status", json={"status_id": 3})
    assert moved.status_code == 200
    assert moved.json()["status_id"] == 3

    listed = client.get("/api/v1/topics")
    assert listed.status_code == 200
    stored = next(item for item in listed.json()["items"] if item["id"] == topic_id)
    assert stored["title"] == "Portón principal"
    assert stored["status_id"] == 3

    deleted = client.delete(f"/api/v1/topics/{topic_id}")
    assert deleted.status_code == 204
    listed_after = client.get("/api/v1/topics")
    assert all(item["id"] != topic_id for item in listed_after.json()["items"])
