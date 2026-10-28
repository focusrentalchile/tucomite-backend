"""End-to-end HTTP tests for session login and platform clients."""

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.access_bootstrap import DEMO_CLIENT_NAME
from tests.helpers.auth import login_as_demo_admin, login_as_super_admin
from tests.helpers.platform_accounts import DEMO_ADMIN_EMAIL, SEED_PASSWORD, SUPER_ADMIN_EMAIL

client = TestClient(app)


def test_login_rejects_bad_password_and_accepts_seeded_accounts() -> None:
    rejected = client.post(
        "/api/v1/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": "wrong-password"},
    )
    assert rejected.status_code == 401

    login_as_super_admin(client)
    session = client.get("/api/v1/auth/session")
    assert session.status_code == 200
    assert session.json()["email"] == SUPER_ADMIN_EMAIL
    assert session.json()["is_super_admin"] is True

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/session").status_code == 401


def test_super_admin_lists_demo_client_and_can_create_another() -> None:
    login_as_super_admin(client)
    listed = client.get("/api/v1/clients")
    assert listed.status_code == 200
    names = {item["name"] for item in listed.json()["items"]}
    assert DEMO_CLIENT_NAME in names

    created = client.post(
        "/api/v1/clients",
        json={
            "name": f"Cliente {uuid.uuid4().hex[:6]}",
            "email": f"admin.{uuid.uuid4().hex[:8]}@demo.local",
            "password": SEED_PASSWORD,
            "license_starts_at": "2026-01-01",
            "license_ends_at": "2027-01-01",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["admin_email"].endswith("@demo.local")
    assert body["license_starts_at"] == "2026-01-01"
    assert body["license_ends_at"] == "2027-01-01"

    client_id = body["id"]
    updated = client.put(
        f"/api/v1/clients/{client_id}",
        json={
            "name": body["name"],
            "email": body["admin_email"],
            "license_starts_at": "2026-02-01",
            "license_ends_at": "2027-02-01",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["license_starts_at"] == "2026-02-01"

    removed = client.delete(f"/api/v1/clients/{client_id}")
    assert removed.status_code == 204
    listed_again = client.get("/api/v1/clients")
    assert client_id not in {item["id"] for item in listed_again.json()["items"]}


def test_demo_admin_cannot_list_clients() -> None:
    login_as_demo_admin(client)
    me = client.get("/api/v1/access/me")
    assert me.status_code == 200
    assert me.json()["email"] == DEMO_ADMIN_EMAIL
    assert me.json()["is_super_admin"] is False

    forbidden = client.get("/api/v1/clients")
    assert forbidden.status_code == 403
