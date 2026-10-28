"""End-to-end HTTP tests for session login and platform clients."""

import uuid

from fastapi.testclient import TestClient

from app.domain.access import SUPER_ADMIN_EMAIL
from app.main import app
from app.services.access_bootstrap import DEMO_ADMIN_EMAIL, DEMO_CLIENT_NAME, SEED_PASSWORD
from tests.helpers.auth import login_as_demo_admin, login_as_super_admin

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
        },
    )
    assert created.status_code == 201
    assert created.json()["admin_email"].endswith("@demo.local")


def test_demo_admin_cannot_list_clients() -> None:
    login_as_demo_admin(client)
    me = client.get("/api/v1/access/me")
    assert me.status_code == 200
    assert me.json()["email"] == DEMO_ADMIN_EMAIL
    assert me.json()["is_super_admin"] is False

    forbidden = client.get("/api/v1/clients")
    assert forbidden.status_code == 403
