"""Unit tests for the health service."""

from app.services.health_service import SERVICE_NAME, get_health_status


def test_get_health_status_returns_ok() -> None:
    payload = get_health_status()

    assert payload.status == "ok"
    assert payload.service == SERVICE_NAME
