"""End-to-end HTTP tests for committee members on MySQL."""

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.auth import login_as_demo_admin, login_as_super_admin
from tests.helpers.platform_accounts import SEED_PASSWORD

client = TestClient(app)


def test_committee_user_reads_building_voter_seats() -> None:
    """Committee voters share the same seat count as the building owner."""
    login_as_demo_admin(client)
    owner = client.get("/api/v1/committee/voter-seats")
    assert owner.status_code == 200
    owner_count = owner.json()["count"]
    assert owner_count >= 3

    signed = client.post(
        "/api/v1/auth/login",
        json={"email": "comite@demo.tucomite.local", "password": SEED_PASSWORD},
    )
    assert signed.status_code == 200
    committee = client.get("/api/v1/committee/voter-seats")
    assert committee.status_code == 200
    assert committee.json()["count"] == owner_count


def test_committee_member_can_be_added_listed_and_removed() -> None:
    login_as_super_admin(client)
    users = client.get("/api/v1/users")
    assert users.status_code == 200
    user = users.json()["items"][0]
    user_id = user["id"]

    client.delete(f"/api/v1/committee/members/{user_id}")

    created = client.post("/api/v1/committee/members", json={"user_id": user_id})
    assert created.status_code == 201
    assert created.json()["user_id"] == user_id
    assert created.json()["full_name"] == user["full_name"]

    listed = client.get("/api/v1/committee/members")
    assert listed.status_code == 200
    assert any(item["user_id"] == user_id for item in listed.json()["items"])

    duplicate = client.post("/api/v1/committee/members", json={"user_id": user_id})
    assert duplicate.status_code == 409

    removed = client.delete(f"/api/v1/committee/members/{user_id}")
    assert removed.status_code == 204
    listed_again = client.get("/api/v1/committee/members")
    assert all(item["user_id"] != user_id for item in listed_again.json()["items"])
