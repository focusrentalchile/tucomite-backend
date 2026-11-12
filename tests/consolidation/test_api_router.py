"""Consolidation tests for API composition and route registration."""

from app.api.v1.router import api_router
from app.core.config import settings
from app.main import app


def test_v1_router_includes_health_path() -> None:
    paths = {route.path for route in api_router.routes}

    assert "/health" in paths
    assert "/blog" in paths
    assert "/blog/manage" in paths
    assert "/blog/{slug}" in paths
    assert "/seo/sitemap.xml" in paths
    assert "/contact" in paths
    assert "/contact/messages" in paths
    assert "/access/catalog" in paths
    assert "/roles" in paths
    assert "/roles/{role_id}/permissions" in paths
    assert "/roles/{role_id}" in paths
    assert "/users" in paths
    assert "/users/{user_id}" in paths
    assert "/topics" in paths
    assert "/topics/{topic_id}/votes" in paths
    assert "/topics/{topic_id}/opinions" in paths
    assert "/access/me" in paths
    assert "/committee/members" in paths
    assert "/committee/members/{user_id}" in paths
    assert "/periods" in paths
    assert "/periods/{period_id}/close" in paths
    assert "/projects" in paths
    assert "/projects/{project_id}" in paths
    assert "/reports/summary" in paths
    assert "/management/tasks" in paths
    assert "/management/tasks/{task_id}" in paths
    assert "/management/tasks/{task_id}/messages" in paths
    assert "/management/tasks/{task_id}/status" in paths
    assert "/management/workspace/clients" in paths
    assert "/clients" in paths
    assert "/clients/register" in paths
    assert "/clients/{client_id}/renew-license" in paths
    assert "/auth/change-password" in paths
    assert "/auth/activate" in paths
    assert "/management/workspace/imports" in paths
    assert "/management/workspace/imports/{import_id}/approve" in paths
    assert "/management/workspace/imports/{import_id}/reject" in paths
    assert "/message-types" in paths
    assert "/messages" in paths
    assert "/messages/{message_id}" in paths
    assert "/messages/{message_id}/open" in paths
    assert "/messages/{message_id}/status" in paths
    assert "/messages/{message_id}/replies" in paths
    assert "/messages/{message_id}/appeal" in paths
    assert "/notifications" in paths
    assert "/notifications/{notification_id}/read" in paths
    assert "/agreements" in paths
    assert "/agreements/{agreement_id}" in paths
    assert "/agreements/{agreement_id}/pdf" in paths
    assert "/legal-cases" in paths
    assert "/legal-cases/{case_id}" in paths
    assert "/legal-cases/{case_id}/open" in paths
    assert "/legal-cases/{case_id}/status" in paths
    assert "/legal-cases/{case_id}/messages" in paths
    assert "/support/types" in paths
    assert "/support/tickets" in paths
    assert "/support/tickets/{ticket_id}" in paths
    assert "/support/statuses" in paths
    assert "/support/tickets/{ticket_id}/replies" in paths
    assert "/support/tickets/{ticket_id}/replies/{reply_id}" in paths
    assert "/support/tickets/{ticket_id}/status" in paths
    assert "/building-wall/posts" in paths
    assert "/building-wall/posts/{post_id}" in paths
    assert "/platform-settings" in paths
    assert "/account/close" in paths
    assert "/building-settings/vote-window" in paths


def test_application_mounts_v1_prefix() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    assert f"{settings.api_v1_prefix}/health" in paths


def test_cors_allows_frontend_and_admin() -> None:
    assert "http://127.0.0.1:5173" in settings.cors_origins
    assert "http://127.0.0.1:5174" in settings.cors_origins
    assert "https://tucomite.cl" in settings.cors_origins
    assert "https://tucomite-admin.web.app" in settings.cors_origins
