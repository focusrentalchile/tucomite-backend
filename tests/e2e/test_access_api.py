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
    assert modules["roles"] == ["view", "create", "update", "delete"]
    assert modules["clients"] == ["view", "create", "update", "delete"]
    assert modules["agreements"] == ["view", "vote"]
    assert modules["matters"] == ["create", "comment"]
    assert modules["tasks"] == ["assign"]
    assert modules["progress"] == ["view", "update"]
    assert modules["documents"] == ["view"]
    assert modules["notifications"] == ["receive"]
    assert modules["support"] == ["view", "create", "reply", "update"]


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


def test_building_roles_hide_super_admin_and_custom_role_can_be_deleted() -> None:
    login_as_super_admin(client)
    roles = client.get("/api/v1/roles")
    assert roles.status_code == 200
    items = roles.json()["items"]
    names = {item["name"] for item in items}
    assert "administrator" in names
    assert "committee" in names
    assert "resident" in names
    assert "client" in names
    assert all(item["system"] is False for item in items)
    assert not any(item["name"].casefold() in {"super admin", "super administrador"} for item in items)

    starter = next(item for item in items if item["name"] == "administrator")
    blocked = client.delete(f"/api/v1/roles/{starter['id']}")
    assert blocked.status_code == 409

    custom = client.post("/api/v1/roles", json={"name": f"portero-{uuid.uuid4().hex[:8]}"})
    assert custom.status_code == 201
    deleted = client.delete(f"/api/v1/roles/{custom.json()['id']}")
    assert deleted.status_code == 204

    building_role = next(item for item in items if item["name"] == "resident")
    created = client.post(
        "/api/v1/users",
        json={
            "full_name": "Ana Pérez",
            "email": f"ana.{uuid.uuid4().hex[:8]}@tucomite.local",
            "password": "secreto-1",
            "role_id": building_role["id"],
        },
    )
    assert created.status_code == 201
    assert "password" not in created.json()
    assert created.json()["email"].endswith("@tucomite.local")
    assert created.json()["protected"] is False
