"""End-to-end HTTP tests for platform support tickets."""

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.auth import login_as_demo_admin, login_as_super_admin

client = TestClient(app)


def test_building_admin_opens_ticket_and_staff_replies() -> None:
    login_as_demo_admin(client)
    created = client.post(
        "/api/v1/support/tickets",
        json={"subject": "No puedo votar", "body": "Al abrir acuerdos aparece un error."},
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]
    assert created.json()["status"] == "todo"
    assert created.json()["priority_id"] == 2
    assert created.json()["messages"][0]["from_staff"] is False

    listed = client.get("/api/v1/support/tickets")
    assert listed.status_code == 200
    assert ticket_id in {item["id"] for item in listed.json()["items"]}

    client.post("/api/v1/auth/logout")
    login_as_super_admin(client)
    staff_list = client.get("/api/v1/support/tickets")
    assert staff_list.status_code == 200
    assert ticket_id in {item["id"] for item in staff_list.json()["items"]}

    replied = client.post(
        f"/api/v1/support/tickets/{ticket_id}/messages",
        json={"body": "Revisamos el acceso y ya quedó corregido."},
    )
    assert replied.status_code == 201
    assert replied.json()["status"] == "in_progress"
    assert any(message["from_staff"] for message in replied.json()["messages"])

    closed = client.patch(
        f"/api/v1/support/tickets/{ticket_id}/status",
        json={"status": "done"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "done"
