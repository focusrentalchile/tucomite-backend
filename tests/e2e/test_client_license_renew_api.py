"""HTTP path for renewing an expired client license."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app
from tests.helpers.platform_accounts import ensure_test_platform_accounts


def test_super_admin_renews_expired_license_and_rejects_active() -> None:
    ensure_test_platform_accounts()
    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@tucomite.cl", "password": "123456"},
    )
    assert login.status_code == 200

    today = date.today()
    created = client.post(
        "/api/v1/clients",
        json={
            "name": f"Edificio Renovar {today.isoformat()}",
            "email": f"renew-{today.toordinal()}@edificio.cl",
            "password": "secreto1",
            "address": "Calle 1",
            "responsible_name": "Ana",
            "license_starts_at": (today - timedelta(days=60)).isoformat(),
            "license_ends_at": (today - timedelta(days=1)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    client_id = created.json()["id"]

    renewed = client.post(f"/api/v1/clients/{client_id}/renew-license")
    assert renewed.status_code == 200, renewed.text
    body = renewed.json()
    assert body["license_starts_at"] == today.isoformat()
    assert body["license_ends_at"] == (today + timedelta(days=30)).isoformat()

    blocked = client.post(f"/api/v1/clients/{client_id}/renew-license")
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert detail["code"] == "license_still_active"
    assert detail["days_remaining"] == 30
