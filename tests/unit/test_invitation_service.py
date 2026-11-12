"""Unit tests for invitation status, open tracking, and actor list filters."""

from app.domain.invitations import (
    KIND_BUILDING,
    KIND_PLATFORM,
    STATUS_FAILED,
    STATUS_OPENED,
    STATUS_REGISTERED,
    STATUS_SENT,
    InvitationRecord,
)
from app.services.invitation_service import InvitationService


def _invite(**overrides: object) -> InvitationRecord:
    base = dict(
        id="1",
        kind=KIND_PLATFORM,
        name="Ana",
        email="ana@edificio.cl",
        building_name="",
        role_key="client",
        client_id=None,
        invited_by_user_id="u1",
        token="tok",
        sent_at="2026-01-01T00:00:00",
        opened_at=None,
        registered_at=None,
        created_at="2026-01-01T00:00:00",
    )
    return InvitationRecord(**{**base, **overrides})


class _FakeInvitationRepo:
    def __init__(self, items: list[InvitationRecord]) -> None:
        self._items = items

    def list_all(self) -> list[InvitationRecord]:
        return list(self._items)

    def list_for_client(self, client_id: str) -> list[InvitationRecord]:
        return [item for item in self._items if item.client_id == client_id]


def test_invitation_status_prefers_registered_then_opened() -> None:
    base = _invite()
    assert _invite(sent_at=None).status == STATUS_FAILED
    assert base.status == STATUS_SENT
    assert _invite(opened_at="2026-01-02T00:00:00").status == STATUS_OPENED
    assert (
        _invite(opened_at="2026-01-02T00:00:00", registered_at="2026-01-03T00:00:00").status
        == STATUS_REGISTERED
    )


def test_assignable_invite_roles_exclude_legal() -> None:
    from app.services.invitation_service import ASSIGNABLE_INVITE_ROLES

    assert "legal" not in ASSIGNABLE_INVITE_ROLES
    assert {"administrator", "committee", "caretaker", "resident"} <= ASSIGNABLE_INVITE_ROLES


def test_list_for_actor_hides_platform_invites_from_client() -> None:
    platform = _invite(
        id="p1",
        kind=KIND_PLATFORM,
        client_id="c1",
        email="owner@edificio.cl",
        registered_at="2026-01-02T00:00:00",
    )
    building = _invite(
        id="b1",
        kind=KIND_BUILDING,
        client_id="c1",
        role_key="resident",
        email="residente@edificio.cl",
        invited_by_user_id="owner",
    )
    service = InvitationService(_FakeInvitationRepo([platform, building]), access=None, db=None)

    client_items = service.list_for_actor(is_super_admin=False, client_id="c1")
    assert [item.id for item in client_items] == ["b1"]

    admin_items = service.list_for_actor(is_super_admin=True, client_id=None)
    assert [item.id for item in admin_items] == ["p1"]
