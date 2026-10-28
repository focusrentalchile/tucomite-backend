"""End-to-end HTTP tests for platform management tasks."""

import uuid

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.auth import login_as_demo_admin, login_as_super_admin

client = TestClient(app)


def _login_as_building_administrator() -> tuple[str, str]:
    """Cliente cannot open Gestión; create an administrator in the same building."""
    login_as_demo_admin(client)
    roles = client.get("/api/v1/roles")
    assert roles.status_code == 200
    admin_role = next(item for item in roles.json()["items"] if item["name"] == "administrator")
    email = f"gestor.{uuid.uuid4().hex[:8]}@tucomite.local"
    password = "secreto-1"
    created = client.post(
        "/api/v1/users",
        json={
            "full_name": "Gestor edificio",
            "email": email,
            "password": password,
            "role_id": admin_role["id"],
        },
    )
    assert created.status_code == 201, created.text
    client.post("/api/v1/auth/logout")
    signed = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert signed.status_code == 200, signed.text
    return email, password


def test_building_admin_opens_ticket_and_staff_replies() -> None:
    _login_as_building_administrator()
    created = client.post(
        "/api/v1/management/tasks",
        json={"subject": "No puedo votar", "body": "Al abrir acuerdos aparece un error."},
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert created.json()["status"] == "todo"
    assert created.json()["priority_id"] == 2
    assert created.json()["messages"][0]["from_staff"] is False

    listed = client.get("/api/v1/management/tasks")
    assert listed.status_code == 200
    assert task_id in {item["id"] for item in listed.json()["items"]}

    client.post("/api/v1/auth/logout")
    login_as_super_admin(client)
    staff_list = client.get("/api/v1/management/tasks")
    assert staff_list.status_code == 200
    assert task_id in {item["id"] for item in staff_list.json()["items"]}

    replied = client.post(
        f"/api/v1/management/tasks/{task_id}/messages",
        json={"body": "Revisamos el acceso y ya quedó corregido."},
    )
    assert replied.status_code == 201
    assert replied.json()["status"] == "in_progress"
    assert any(message["from_staff"] for message in replied.json()["messages"])

    closed = client.patch(
        f"/api/v1/management/tasks/{task_id}/status",
        json={"status": "done"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "done"


def test_administrator_imports_client_with_owner_approval() -> None:
    login_as_super_admin(client)
    owner_email = f"owner.{uuid.uuid4().hex[:8]}@tucomite.local"
    building = client.post(
        "/api/v1/clients",
        json={
            "name": f"Edificio {uuid.uuid4().hex[:6]}",
            "email": owner_email,
            "password": "secreto-1",
            "license_starts_at": "2026-01-01",
            "license_ends_at": "2027-01-01",
        },
    )
    assert building.status_code == 201, building.text
    imported_client_id = building.json()["id"]
    client.post("/api/v1/auth/logout")

    admin_email, admin_password = _login_as_building_administrator()
    workspace = client.get("/api/v1/management/workspace/clients")
    assert workspace.status_code == 200
    assert imported_client_id not in {item["client_id"] for item in workspace.json()["items"]}

    requested = client.post(
        "/api/v1/management/workspace/imports",
        json={"owner_email": owner_email},
    )
    assert requested.status_code == 201, requested.text
    import_id = requested.json()["id"]
    assert requested.json()["status"] == "pending"
    client.post("/api/v1/auth/logout")

    signed_owner = client.post(
        "/api/v1/auth/login",
        json={"email": owner_email, "password": "secreto-1"},
    )
    assert signed_owner.status_code == 200, signed_owner.text
    notices = client.get("/api/v1/notifications")
    assert notices.status_code == 200
    assert any(item["kind"] == "management_import_request" for item in notices.json()["items"])
    incoming = client.get("/api/v1/management/workspace/imports", params={"scope": "incoming"})
    assert incoming.status_code == 200
    assert import_id in {item["id"] for item in incoming.json()["items"]}
    approved = client.post(f"/api/v1/management/workspace/imports/{import_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    client.post("/api/v1/auth/logout")

    signed_admin = client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": admin_password},
    )
    assert signed_admin.status_code == 200, signed_admin.text
    workspace_after = client.get("/api/v1/management/workspace/clients")
    assert workspace_after.status_code == 200
    assert imported_client_id in {item["client_id"] for item in workspace_after.json()["items"]}

    created = client.post(
        "/api/v1/management/tasks",
        json={
            "subject": "Tarea del edificio importado",
            "body": "Detalle para el cliente importado.",
            "client_id": imported_client_id,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["client_id"] == imported_client_id

    filtered = client.get("/api/v1/management/tasks", params={"client_id": imported_client_id})
    assert filtered.status_code == 200
    assert created.json()["id"] in {item["id"] for item in filtered.json()["items"]}
