"""HTTP path for platform support tickets and web Mensaje bridge."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.auth import login_as_demo_admin, login_as_super_admin

client = TestClient(app)


def test_committee_creates_ticket_and_super_admin_replies() -> None:
    login_as_demo_admin(client)
    types = client.get("/api/v1/support/types", params={"creatable_only": True})
    assert types.status_code == 200
    items = types.json()["items"]
    assert items
    assert all(item["name"] != "Mensaje" for item in items)
    type_id = items[0]["id"]

    created = client.post(
        "/api/v1/support/tickets",
        json={
            "support_type_id": type_id,
            "subject": "Necesito ayuda",
            "body": "No puedo abrir un periodo",
        },
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["id"]

    listed = client.get("/api/v1/support/tickets")
    assert listed.status_code == 200
    assert any(item["id"] == ticket_id for item in listed.json()["items"])

    client.post("/api/v1/auth/logout")
    login_as_super_admin(client)
    inbox = client.get("/api/v1/support/tickets")
    assert inbox.status_code == 200
    assert any(item["id"] == ticket_id for item in inbox.json()["items"])

    replied = client.post(
        f"/api/v1/support/tickets/{ticket_id}/replies",
        json={"body": "Revisamos tu caso"},
    )
    assert replied.status_code == 201, replied.text
    assert replied.json()["status"] == "answered"
    assert len(replied.json()["replies"]) == 1


def test_contact_creates_mensaje_ticket_and_email_reply() -> None:
    created = client.post(
        "/api/v1/contact",
        json={
            "name": "Pedro Web",
            "email": "pedro.web@example.com",
            "message": "Consulta desde el sitio",
            "privacy_accepted": True,
        },
    )
    assert created.status_code == 201

    login_as_super_admin(client)
    inbox = client.get("/api/v1/support/tickets")
    assert inbox.status_code == 200
    web_tickets = [
        item
        for item in inbox.json()["items"]
        if item["support_type_name"] == "Mensaje" and item["contact_email"] == "pedro.web@example.com"
    ]
    assert web_tickets
    ticket_id = web_tickets[0]["id"]

    with patch("app.services.support_service.send_html_email") as send_mail:
        replied = client.post(
            f"/api/v1/support/tickets/{ticket_id}/replies",
            json={"body": "Gracias por escribirnos"},
        )
        assert replied.status_code == 201, replied.text
        send_mail.assert_called_once()
        assert send_mail.call_args.kwargs["to_email"] == "pedro.web@example.com"
