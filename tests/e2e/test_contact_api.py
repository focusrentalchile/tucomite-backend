"""HTTP path for public contact submissions and super-admin inbox."""

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.auth import login_as_super_admin

client = TestClient(app)


def test_contact_message_requires_privacy_and_lists_for_super_admin() -> None:
    denied = client.post(
        "/api/v1/contact",
        json={
            "name": "Ana",
            "email": "ana@edificio.cl",
            "message": "Quiero una demo",
            "privacy_accepted": False,
        },
    )
    assert denied.status_code == 422

    created = client.post(
        "/api/v1/contact",
        json={
            "name": "Ana",
            "email": "ana@edificio.cl",
            "message": "Quiero una demo",
            "privacy_accepted": True,
        },
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["privacy_accepted"] is True
    assert payload["privacy_accepted_at"]

    login_as_super_admin(client)
    listed = client.get("/api/v1/contact/messages")
    assert listed.status_code == 200
    emails = [item["email"] for item in listed.json()["items"]]
    assert "ana@edificio.cl" in emails
