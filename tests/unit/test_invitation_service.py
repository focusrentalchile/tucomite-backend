"""Unit tests for invitation status and open tracking."""

from app.domain.invitations import (
    STATUS_FAILED,
    STATUS_OPENED,
    STATUS_REGISTERED,
    STATUS_SENT,
    InvitationRecord,
)


def test_invitation_status_prefers_registered_then_opened() -> None:
    base = dict(
        id="1",
        kind="platform",
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
    assert InvitationRecord(**{**base, "sent_at": None}).status == STATUS_FAILED
    assert InvitationRecord(**base).status == STATUS_SENT
    assert InvitationRecord(**{**base, "opened_at": "2026-01-02T00:00:00"}).status == STATUS_OPENED
    assert (
        InvitationRecord(
            **{**base, "opened_at": "2026-01-02T00:00:00", "registered_at": "2026-01-03T00:00:00"},
        ).status
        == STATUS_REGISTERED
    )
