"""Helpers to open a signed-in TestClient session."""

from fastapi.testclient import TestClient

from app.domain.access import SUPER_ADMIN_EMAIL
from app.services.access_bootstrap import DEMO_ADMIN_EMAIL, SEED_PASSWORD


def login_as_super_admin(client: TestClient) -> None:
    """Sign in as the seeded platform super admin."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": SEED_PASSWORD},
    )
    assert response.status_code == 200, response.text


def login_as_demo_admin(client: TestClient) -> None:
    """Sign in as the seeded building administrator."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_ADMIN_EMAIL, "password": SEED_PASSWORD},
    )
    assert response.status_code == 200, response.text
