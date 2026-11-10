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


def test_building_admin_creates_ticket_with_attachments_and_reply_files() -> None:
    _login_as_building_administrator()
    created = client.post(
        "/api/v1/management/tasks",
        json={
            "subject": "Cotización de ascensor",
            "body": "Adjunto las cotizaciones.",
            "attachments": [
                {"kind": "file", "name": "cotizacion.pdf", "url": "data:application/pdf;base64,aaa"},
                {"kind": "file", "name": "gastos.xlsx", "url": "data:application/vnd.ms-excel;base64,bbb"},
                {"kind": "image", "name": "ascensor.jpg", "url": "data:image/jpeg;base64,ccc"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    assert {item["name"] for item in created.json()["attachments"]} == {
        "cotizacion.pdf",
        "gastos.xlsx",
        "ascensor.jpg",
    }

    replied = client.post(
        f"/api/v1/management/tasks/{task_id}/messages",
        json={
            "body": "Falta el acta.",
            "attachments": [{"kind": "file", "name": "acta.doc", "url": "data:application/msword;base64,ddd"}],
        },
    )
    assert replied.status_code == 201, replied.text
    # Messages created within the same second have no stable order, so match by body.
    reply = next(item for item in replied.json()["messages"] if item["body"] == "Falta el acta.")
    first = next(item for item in replied.json()["messages"] if item["body"] == "Adjunto las cotizaciones.")
    assert [item["name"] for item in reply["attachments"]] == ["acta.doc"]
    assert first["attachments"] == []
    assert len(replied.json()["attachments"]) == 3

    read = client.get(f"/api/v1/management/tasks/{task_id}")
    assert read.status_code == 200
    assert len(read.json()["attachments"]) == 3

    deleted = client.delete(f"/api/v1/management/tasks/{task_id}")
    assert deleted.status_code == 204


def test_ticket_rejects_unsupported_file_types() -> None:
    _login_as_building_administrator()

    response = client.post(
        "/api/v1/management/tasks",
        json={
            "subject": "Archivo raro",
            "body": "No debería entrar.",
            "attachments": [{"kind": "file", "name": "programa.exe", "url": "data:application/x;base64,aaa"}],
        },
    )

    assert response.status_code == 422


def test_building_admin_deletes_own_ticket() -> None:
    _login_as_building_administrator()
    created = client.post(
        "/api/v1/management/tasks",
        json={"subject": "Borrar esta tarea", "body": "Solo para probar el borrado."},
    )
    assert created.status_code == 201
    task_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/management/tasks/{task_id}")
    assert deleted.status_code == 204

    missing = client.get(f"/api/v1/management/tasks/{task_id}")
    assert missing.status_code == 404


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
    client.post("/api/v1/auth/logout")

    signed_owner_again = client.post(
        "/api/v1/auth/login",
        json={"email": owner_email, "password": "secreto-1"},
    )
    assert signed_owner_again.status_code == 200, signed_owner_again.text
    managers = client.get("/api/v1/management/workspace/administrators")
    assert managers.status_code == 200, managers.text
    manager_ids = {item["user_id"] for item in managers.json()["items"]}
    imported_row = next(
        item for item in managers.json()["items"] if item["import_id"] == import_id
    )
    assert imported_row["home"] is False
    assert imported_row["email"] == admin_email
    assert imported_row["user_id"] in manager_ids

    revoked = client.post(f"/api/v1/management/workspace/imports/{import_id}/revoke")
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "revoked"
    managers_after = client.get("/api/v1/management/workspace/administrators")
    assert managers_after.status_code == 200
    assert import_id not in {
        item["import_id"] for item in managers_after.json()["items"] if item["import_id"]
    }
    client.post("/api/v1/auth/logout")

    signed_admin_again = client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": admin_password},
    )
    assert signed_admin_again.status_code == 200, signed_admin_again.text
    workspace_revoked = client.get("/api/v1/management/workspace/clients")
    assert workspace_revoked.status_code == 200
    assert imported_client_id not in {
        item["client_id"] for item in workspace_revoked.json()["items"]
    }

    reopened = client.post(
        "/api/v1/management/workspace/imports",
        json={"owner_email": owner_email},
    )
    assert reopened.status_code == 201, reopened.text
    assert reopened.json()["id"] == import_id
    assert reopened.json()["status"] == "pending"
    client.post("/api/v1/auth/logout")

    signed_owner_third = client.post(
        "/api/v1/auth/login",
        json={"email": owner_email, "password": "secreto-1"},
    )
    assert signed_owner_third.status_code == 200, signed_owner_third.text
    managers_pending = client.get("/api/v1/management/workspace/administrators")
    assert managers_pending.status_code == 200
    pending_row = next(item for item in managers_pending.json()["items"] if item["import_id"] == import_id)
    assert pending_row["status"] == "pending"
