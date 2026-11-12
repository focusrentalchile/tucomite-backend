"""Unit tests for client license renewal rules."""

from datetime import date

from app.domain.access import ClientRecord, UserRecord
from app.services.client_service import ClientService, LicenseStillActive


class MemoryClients:
    def __init__(self, client: ClientRecord) -> None:
        self.client = client

    def list_clients(self) -> list[ClientRecord]:
        return [self.client]

    def get_client(self, client_id: str) -> ClientRecord | None:
        return self.client if self.client.id == client_id else None

    def save_client(self, client: ClientRecord) -> ClientRecord:
        self.client = client
        return client

    def delete_client(self, client_id: str) -> None:
        raise NotImplementedError


class MemoryAccess:
    def __init__(self, admin: UserRecord) -> None:
        self.admin = admin

    def get_user(self, user_id: str) -> UserRecord | None:
        return self.admin if self.admin.id == user_id else None


def _service(*, ends_at: str) -> ClientService:
    client = ClientRecord(
        id="c1",
        name="Edificio Centro",
        admin_user_id="u1",
        address="Av. 1",
        responsible_name="Ana",
        license_starts_at="2025-01-01",
        license_ends_at=ends_at,
    )
    admin = UserRecord(
        id="u1",
        full_name="Ana",
        email="ana@edificio.cl",
        password_hash="x",
        role_id="r1",
        client_id="c1",
    )
    return ClientService(MemoryClients(client), MemoryAccess(admin))


def test_renew_license_extends_thirty_days_when_expired() -> None:
    service = _service(ends_at="2026-01-01")
    updated, _admin = service.renew_license("c1", today=date(2026, 11, 12))
    assert updated.license_starts_at == "2026-11-12"
    assert updated.license_ends_at == "2026-12-12"


def test_renew_license_rejects_active_window() -> None:
    service = _service(ends_at="2026-12-01")
    try:
        service.renew_license("c1", today=date(2026, 11, 12))
        assert False, "expected LicenseStillActive"
    except LicenseStillActive as error:
        assert error.days_remaining == 19
