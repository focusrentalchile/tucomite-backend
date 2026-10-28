"""End-to-end HTTP tests for roles, permissions, and users on MySQL."""

import uuid

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.auth import login_as_super_admin

client = TestClient(app)


def test_catalog_lists_modules_as_rows_of_functionalities() -> None:
    login_as_super_admin(client)
    response = client.get("/api/v1/access/catalog")

    assert response.status_code == 200
    modules = {item["key"]: item["functionalities"] for item in response.json()["modules"]}
    assert modules["users"] == ["view", "create"]
    assert modules["roles"] == ["view", "create", "update"]
    assert modules["clients"] == ["view", "create"]
    assert modules["agreements"] == ["view", "vote"]
    assert modules["matters"] == ["create", "comment"]
    assert modules["tasks"] == ["assign"]
    assert modules["progress"] == ["view", "update"]
    assert modules["documents"] == ["view"]
    assert modules["notifications"] == ["receive"]


def test_checkbox_persists_a_permission_without_a_second_save() -> None:
    login_as_super_admin(client)
    created = client.post("/api/v1/roles", json={"name": f"role {uuid.uuid4().hex[:8]}"})
    assert created.status_code == 201
    role_id = created.json()["id"]
    assert created.json()["permissions"] == []

    granted = client.patch(
        f"/api/v1/roles/{role_id}/permissions",
        json={"module_key": "users", "functionality_key": "create", "granted": True},
    )

    assert granted.status_code == 200
    assert granted.json()["permissions"] == ["users.create"]

    listed = client.get("/api/v1/roles")
    stored = next(item for item in listed.json()["items"] if item["id"] == role_id)
    assert stored["permissions"] == ["users.create"]


def test_system_role_cannot_be_edited_and_user_can_be_created() -> None:
    login_as_super_admin(client)
    roles = client.get("/api/v1/roles")
    system_role = next(item for item in roles.json()["items"] if item["system"] is True)

    rejected = client.patch(
        f"/api/v1/roles/{system_role['id']}/permissions",
        json={"module_key": "users", "functionality_key": "view", "granted": False},
    )
    assert rejected.status_code == 409

    created = client.post(
        "/api/v1/users",
        json={
            "full_name": "Ana Pérez",
            "email": f"ana.{uuid.uuid4().hex[:8]}@tucomite.local",
            "password": "secreto-1",
            "role_id": system_role["id"],
        },
    )
    assert created.status_code == 201
    assert "password" not in created.json()
    assert created.json()["email"].endswith("@tucomite.local")
