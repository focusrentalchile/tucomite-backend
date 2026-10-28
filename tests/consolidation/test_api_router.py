"""Consolidation tests for API composition and route registration."""

from app.api.v1.router import api_router
from app.core.config import settings
from app.main import app


def test_v1_router_includes_health_path() -> None:
    paths = {route.path for route in api_router.routes}

    assert "/health" in paths
    assert "/access/catalog" in paths
    assert "/roles" in paths
    assert "/roles/{role_id}/permissions" in paths
    assert "/roles/{role_id}" in paths
    assert "/users" in paths
    assert "/users/{user_id}" in paths
    assert "/topics" in paths
    assert "/topics/{topic_id}/votes" in paths
    assert "/access/me" in paths
    assert "/committee/members" in paths
    assert "/committee/members/{user_id}" in paths
    assert "/periods" in paths
    assert "/periods/{period_id}/close" in paths
    assert "/projects" in paths
    assert "/projects/{project_id}" in paths
    assert "/reports/summary" in paths
    assert "/support/tickets" in paths
    assert "/support/tickets/{ticket_id}" in paths
    assert "/support/tickets/{ticket_id}/messages" in paths
    assert "/support/tickets/{ticket_id}/status" in paths


def test_application_mounts_v1_prefix() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    assert f"{settings.api_v1_prefix}/health" in paths


def test_cors_allows_frontend_and_admin() -> None:
    assert "http://127.0.0.1:5173" in settings.cors_origins
    assert "http://127.0.0.1:5174" in settings.cors_origins
    assert "https://tucomite.cl" in settings.cors_origins
    assert "https://tucomite-admin.web.app" in settings.cors_origins
