"""Unit tests for reusing a client email after the building was removed."""

from dataclasses import dataclass

from app.domain.access import ClientRecord, UserRecord
from app.services.client_service import ClientService


@dataclass
class FakeClients:
    clients: dict[str, ClientRecord]

    def get_client(self, client_id: str) -> ClientRecord | None:
        return self.clients.get(client_id)


@dataclass
class FakeAccess:
    users: dict[str, UserRecord]

    def list_users(self) -> list[UserRecord]:
        return list(self.users.values())

    def get_user_by_email(self, email: str) -> UserRecord | None:
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    def delete_user(self, user_id: str) -> None:
        self.users.pop(user_id, None)


def test_release_email_removes_orphan_user_from_deleted_building() -> None:
    orphan = UserRecord(
        id="orphan-user",
        full_name="Huérfano",
        email="reuse@demo.local",
        password_hash="x",
        role_id="role-client",
        client_id="missing-client",
    )
    access = FakeAccess(users={"orphan-user": orphan})
    clients = FakeClients(clients={})
    service = ClientService(clients, access)

    service._release_email_if_orphaned("reuse@demo.local")

    assert access.users == {}


def test_release_email_keeps_active_building_owner_for_other_buildings() -> None:
    active_client = ClientRecord(
        id="c1",
        name="Activo",
        admin_user_id="u1",
        license_starts_at="2026-01-01",
        license_ends_at="2027-01-01",
    )
    active_user = UserRecord(
        id="u1",
        full_name="Dueño",
        email="taken@demo.local",
        password_hash="x",
        role_id="role-client",
        client_id="c1",
    )
    access = FakeAccess(users={"u1": active_user})
    clients = FakeClients(clients={"c1": active_client})
    service = ClientService(clients, access)

    service._release_email_if_orphaned("taken@demo.local")

    assert "u1" in access.users
