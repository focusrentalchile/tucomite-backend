"""Aggregates every v1 endpoint router."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    access,
    account,
    agreements,
    auth,
    blog,
    building_wall,
    client_settings,
    clients,
    committee,
    contact,
    email_templates,
    management,
    health,
    invitations,
    legal,
    messages,
    notifications,
    periods,
    platform_settings,
    projects,
    reports,
    seo,
    support,
    topics,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(access.router)
api_router.include_router(account.router)
api_router.include_router(client_settings.router)
api_router.include_router(blog.router)
api_router.include_router(seo.router)
api_router.include_router(clients.router)
api_router.include_router(contact.router)
api_router.include_router(committee.router)
api_router.include_router(periods.router)
api_router.include_router(projects.router)
api_router.include_router(reports.router)
api_router.include_router(management.router)
api_router.include_router(messages.router)
api_router.include_router(notifications.router)
api_router.include_router(legal.router)
api_router.include_router(support.router)
api_router.include_router(building_wall.router)
api_router.include_router(platform_settings.router)
api_router.include_router(email_templates.router)
api_router.include_router(invitations.router)
api_router.include_router(topics.router)
api_router.include_router(agreements.router)
