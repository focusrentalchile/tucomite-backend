"""Consolidation: invitations router is registered on the API."""

from app.api.v1.router import api_router


def test_invitations_routes_are_registered() -> None:
    paths = {getattr(route, "path", "") for route in api_router.routes}
    assert any("/invitations" in path for path in paths)
    assert any("by-token" in path for path in paths)
    assert any("track" in path for path in paths)
