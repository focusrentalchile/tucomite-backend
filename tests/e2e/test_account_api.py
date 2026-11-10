"""End-to-end HTTP tests for closing a building owner's account."""

import base64
import io
import json
import uuid
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.auth import login_as_demo_admin, login_as_super_admin
from tests.helpers.platform_accounts import SEED_PASSWORD

client = TestClient(app)

OWNER_PASSWORD = "secreto-1"
PHOTO = base64.b64encode(b"fake-jpeg-bytes").decode()


def _create_building() -> tuple[str, str]:
    """Open a fresh building so closing its owner never touches the shared demo accounts."""
    login_as_super_admin(client)
    owner_email = f"owner.{uuid.uuid4().hex[:8]}@tucomite.local"
    created = client.post(
        "/api/v1/clients",
        json={
            "name": f"Edificio Baja {uuid.uuid4().hex[:6]}",
            "email": owner_email,
            "password": OWNER_PASSWORD,
            "license_starts_at": "2026-01-01",
            "license_ends_at": "2027-12-31",
        },
    )
    assert created.status_code == 201, created.text
    client.post("/api/v1/auth/logout")
    return owner_email, created.json()["id"]


def _login(email: str, password: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_close_requires_a_session() -> None:
    client.post("/api/v1/auth/logout")

    response = client.post("/api/v1/account/close", json={"reason": "Me voy", "password": "x"})

    assert response.status_code == 401


def test_only_the_client_role_can_close_an_account() -> None:
    signed = _login("comite@demo.tucomite.local", SEED_PASSWORD)
    assert signed.status_code == 200, signed.text

    response = client.post(
        "/api/v1/account/close",
        json={"reason": "Me voy", "password": SEED_PASSWORD},
    )

    assert response.status_code == 403
    assert "building owner" in response.json()["detail"]
    assert _login("comite@demo.tucomite.local", SEED_PASSWORD).status_code == 200


def test_super_admin_cannot_close_an_account() -> None:
    login_as_super_admin(client)

    response = client.post(
        "/api/v1/account/close",
        json={"reason": "Me voy", "password": SEED_PASSWORD},
    )

    assert response.status_code == 403


def test_wrong_password_keeps_the_account_open() -> None:
    login_as_demo_admin(client)

    response = client.post(
        "/api/v1/account/close",
        json={"reason": "Me voy", "password": "incorrecta"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid password."
    assert client.get("/api/v1/access/me").status_code == 200
    login_as_demo_admin(client)


def test_reason_is_required() -> None:
    login_as_demo_admin(client)

    response = client.post("/api/v1/account/close", json={"reason": "", "password": SEED_PASSWORD})

    assert response.status_code == 422
    blank = client.post("/api/v1/account/close", json={"reason": "   ", "password": SEED_PASSWORD})
    assert blank.status_code == 422
    assert client.get("/api/v1/access/me").status_code == 200


def test_owner_closes_account_gets_zip_and_cannot_sign_in_again() -> None:
    owner_email, client_id = _create_building()
    assert _login(owner_email, OWNER_PASSWORD).status_code == 200
    created = client.post(
        "/api/v1/topics",
        json={
            "title": "Pintura del hall",
            "description": "Hay que pintar.",
            "category_key": "maintenance",
            "attachment_name": "hall.jpg",
            "decision": "¿Contratamos pintor?",
            "priority_id": 2,
            "attachments": [
                {"kind": "image", "name": "hall.jpg", "url": f"data:image/jpeg;base64,{PHOTO}"},
                {"kind": "file", "name": "cotizacion.pdf", "url": f"data:application/pdf;base64,{PHOTO}"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["client_id"] == client_id

    response = client.post(
        "/api/v1/account/close",
        json={"reason": "Vendimos el edificio", "password": OWNER_PASSWORD},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert ".zip" in response.headers["content-disposition"]
    archive = ZipFile(io.BytesIO(response.content))
    names = archive.namelist()
    assert "manifest.json" in names
    assert "users/summary.json" in names
    assert any(name.startswith("topics/pintura-del-hall-") and name.endswith("/topic.json") for name in names)
    photo = next(name for name in names if name.endswith("/photos/hall.jpg"))
    assert archive.read(photo) == b"fake-jpeg-bytes"
    assert any(name.endswith("/files/cotizacion.pdf") for name in names)
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["client_id"] == client_id
    assert manifest["counts"]["topics"] == 1
    users = json.loads(archive.read("users/summary.json"))
    assert owner_email in {item["email"] for item in users}
    assert all("password" not in key for item in users for key in item)

    assert client.get("/api/v1/access/me").status_code == 401
    blocked = _login(owner_email, OWNER_PASSWORD)
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "account_closed"


def test_closing_twice_is_not_possible() -> None:
    owner_email, _ = _create_building()
    assert _login(owner_email, OWNER_PASSWORD).status_code == 200
    first = client.post(
        "/api/v1/account/close",
        json={"reason": "Prueba", "password": OWNER_PASSWORD},
    )
    assert first.status_code == 200, first.text

    again = client.post(
        "/api/v1/account/close",
        json={"reason": "Prueba", "password": OWNER_PASSWORD},
    )

    assert again.status_code == 401
